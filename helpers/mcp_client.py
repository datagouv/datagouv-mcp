"""
Common helper to invoke an MCP tool call with the given params.
"""

import os

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult


async def call_tool_on_mcp(tool_name: str, params: dict) -> CallToolResult:
    port = os.getenv("MCP_PORT", "8000")
    url = f"http://localhost:{port}/mcp"

    async with streamable_http_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, params)

    return result
