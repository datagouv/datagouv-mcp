import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from typing import Awaitable, Callable

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from helpers.matomo import track_matomo
from tools import register_tools

# Configure logging
LOGGER_NAME = "datagouv_mcp"


def _resolve_log_level(level_name: str) -> int:
    """Resolve a log level name to a numeric logging level."""
    return getattr(logging, level_name.upper(), logging.INFO)


logging.basicConfig(
    level=_resolve_log_level(os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(LOGGER_NAME)

# Configure transport security for DNS rebinding protection (mcp >= 1.23)
# Per MCP spec: MUST validate Origin header, SHOULD bind to localhost when running locally
# Allow connections from production domain and localhost for development
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[
        "mcp.data.gouv.fr",
        "mcp.preprod.data.gouv.fr",
        "localhost",
        "127.0.0.1",
    ],
    # Validate Origin header to prevent DNS rebinding attacks (MCP spec requirement)
    allowed_origins=[
        "https://mcp.data.gouv.fr",
        "https://mcp.preprod.data.gouv.fr",
        "http://localhost:*",
        "http://127.0.0.1:*",
    ],
)

mcp = FastMCP("data.gouv.fr MCP server", transport_security=transport_security)
register_tools(mcp)


def with_monitoring(
    inner_app: Callable[[dict, Callable, Callable], Awaitable[None]],
):
    async def app(scope, receive, send):
        # We only track HTTP requests (The /mcp endpoint and others)
        if scope["type"] == "http":
            path: str = scope.get("path", "")

            # Handle /health endpoint (no tracking)
            if path == "/health":
                timestamp = datetime.now(timezone.utc).isoformat()
                # Get version from package metadata (managed by setuptools-scm)
                try:
                    app_version = version("datagouv-mcp")
                except PackageNotFoundError:
                    app_version = "unknown"

                body = json.dumps(
                    {"status": "ok", "timestamp": timestamp, "version": app_version}
                ).encode("utf-8")
                headers = [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("utf-8")),
                ]
                await send(
                    {"type": "http.response.start", "status": 200, "headers": headers}
                )
                await send({"type": "http.response.body", "body": body})
                return

            # Matomo Tracking for /mcp requests
            # Convert ASGI headers list to a dictionary for the helper
            headers_dict: dict[str, str] = {
                k.decode("utf-8"): v.decode("utf-8")
                for k, v in scope.get("headers", [])
            }

            # Construct the full URL
            host: str = headers_dict.get("host", "localhost")
            full_url: str = f"https://{host}{path}"

            # Fire the tracking task in the background
            # Since path is always /mcp, the helper will log "MCP Request: /mcp"
            asyncio.create_task(
                track_matomo(url=full_url, path=path, headers=headers_dict)
            )

        # Continue the MCP server logic
        await inner_app(scope, receive, send)

    return app


asgi_app = with_monitoring(mcp.streamable_http_app())


# Run with streamable HTTP transport
if __name__ == "__main__":
    port_str = os.getenv("MCP_PORT", "8000")
    try:
        port = int(port_str)
    except ValueError:
        print(
            f"Error: Invalid MCP_PORT environment variable: {port_str}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Per MCP spec: SHOULD bind to localhost when running locally
    # Default to 0.0.0.0 for production (no breaking change)
    # Set MCP_HOST=127.0.0.1 for local development to follow MCP security best practices
    host = os.getenv("MCP_HOST", "0.0.0.0")
    uvicorn.run(asgi_app, host=host, port=port, log_level="info")
