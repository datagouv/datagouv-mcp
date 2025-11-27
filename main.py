import logging
import os
import sys

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
    uvicorn.run(mcp.streamable_http_app(), host="0.0.0.0", port=port, log_level="info")
