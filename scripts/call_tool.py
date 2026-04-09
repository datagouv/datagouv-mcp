"""
CLI helper to call any MCP tool without manual curl handshaking.

Usage:
    python scripts/call_tool.py <tool_name> '<json_args>'

Example:
    python scripts/call_tool.py search_datasets '{"query": "IRVE"}'
    python scripts/call_tool.py get_resource_info '{"resource_id": "abc123"}'
"""

import asyncio
import json
import logging
import os
import sys

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import TextContent

from helpers.logging import MAIN_LOGGER_NAME

logger = logging.getLogger(MAIN_LOGGER_NAME)


async def call_tool(tool_name: str, args: dict) -> None:
    """
    Connect to MCP server and call a tool with given arguments.
    """
    logger.debug("Initiating tool call: %s", tool_name)
    port = os.getenv("MCP_PORT", "8000")
    url = f"http://localhost:{port}/mcp"

    async with streamable_http_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, args)
            if result.content and isinstance(result.content[0], TextContent):
                print(result.content[0].text)
            elif not result.content:
                print(f"Error: empty response from tool '{tool_name}'", file=sys.stderr)
            else:
                print(
                    f"Error: unexpected content type from tool '{tool_name}': {type(result.content[0]).__name__}",
                    file=sys.stderr,
                )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/call_tool.py <tool_name> '<json_args>'")
        sys.exit(1)
    tool = sys.argv[1]
    arguments = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    asyncio.run(call_tool(tool, arguments))
