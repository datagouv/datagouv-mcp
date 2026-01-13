import json
import logging
import os
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from typing import Awaitable, Callable

import uvicorn
from mcp.server.fastmcp import FastMCP

from tools import register_tools

# Configure logging
LOGGER_NAME = "datagouv_mcp"
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(LOGGER_NAME)
logger.setLevel(logging.DEBUG)

mcp = FastMCP("data.gouv.fr MCP server")
register_tools(mcp)


def with_health_endpoint(
    inner_app: Callable[[dict, Callable, Callable], Awaitable[None]],
):
    async def app(scope, receive, send):
        if scope["type"] == "http" and scope.get("path") == "/health":
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

        await inner_app(scope, receive, send)

    return app


asgi_app = with_health_endpoint(mcp.streamable_http_app())


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
    uvicorn.run(asgi_app, host="0.0.0.0", port=port, log_level="info")
