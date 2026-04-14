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

from helpers.health_probe import _run_health_check
from helpers.logging import MAIN_LOGGER_NAME, UVICORN_LOGGING_CONFIG
from helpers.matomo import (
    apply_matomo_request_context,
    reset_matomo_request_context,
    track_matomo_request,
)
from helpers.sentry import init_sentry
from tools import register_tools

init_sentry()

SERVER_START_TIME = datetime.now(timezone.utc)

logger = logging.getLogger(MAIN_LOGGER_NAME)

# Configure transport security for DNS rebinding protection (mcp >= 1.23)
# Per MCP spec: MUST validate Origin header, SHOULD bind to localhost when running locally
# Allow connections from production domain and localhost for development
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[
        "mcp.data.gouv.fr",
        "mcp.preprod.data.gouv.fr",
        "localhost:*",
        "127.0.0.1:*",
    ],
    # Validate Origin header to prevent DNS rebinding attacks (MCP spec requirement)
    allowed_origins=[
        "https://mcp.data.gouv.fr",
        "https://mcp.preprod.data.gouv.fr",
        "http://localhost:*",
        "http://127.0.0.1:*",
    ],
)

# Enable stateless_http to avoid "Session not found" errors with MCP clients
# that don't properly maintain the mcp-session-id header across requests
# (e.g. Claude Code, Cline, OpenAI Codex). Since this server does not use
# server-initiated notifications, stateful sessions are not needed.
mcp = FastMCP(
    "data.gouv.fr MCP server",
    transport_security=transport_security,
    stateless_http=True,
)
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
                # Get version from package metadata (managed by setuptools-scm)
                try:
                    app_version = version("datagouv-mcp")
                except PackageNotFoundError:
                    app_version = "unknown"

                is_healthy = await _run_health_check()
                if is_healthy:
                    body = json.dumps(
                        {
                            "status": "ok",
                            "uptime_since": SERVER_START_TIME.isoformat(),
                            "version": app_version,
                            "env": os.getenv("MCP_ENV", "unknown"),
                            "data_env": os.getenv("DATAGOUV_API_ENV", "unknown"),
                        }
                    ).encode("utf-8")
                    http_status = 200
                else:
                    body = json.dumps({"status": "mcp_unavailable"}).encode("utf-8")
                    http_status = 503

                headers = [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("utf-8")),
                ]
                await send(
                    {
                        "type": "http.response.start",
                        "status": http_status,
                        "headers": headers,
                    }
                )
                await send({"type": "http.response.body", "body": body})
                return

            # Matomo: bind request URL/UA for tool event tracking; HTTP-level hit in background
            headers_dict: dict[str, str] = {
                k.decode("utf-8"): v.decode("utf-8")
                for k, v in scope.get("headers", [])
            }
            url_token, ua_token = apply_matomo_request_context(headers_dict, path)
            host: str = headers_dict.get("host", "localhost")
            full_url: str = f"https://{host}{path}"
            try:
                asyncio.create_task(
                    track_matomo_request(url=full_url, path=path, headers=headers_dict)
                )
                await inner_app(scope, receive, send)
            finally:
                reset_matomo_request_context(url_token, ua_token)
            return

        # Continue the MCP server logic (non-HTTP scopes, e.g. lifespan)
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
    uvicorn.run(
        asgi_app,
        host=host,
        port=port,
        log_level="info",
        log_config=UVICORN_LOGGING_CONFIG,
    )
