"""Tests for the MCP server endpoints and tools."""

import os
from typing import Any

import aiohttp
import pytest


@pytest.fixture(scope="session")
def mcp_server_port() -> int:
    """Get the MCP server port from environment or use default."""
    return int(os.getenv("MCP_PORT", "8000"))


@pytest.fixture(scope="session")
def mcp_server_url(mcp_server_port: int) -> str:
    """Get the MCP server URL."""
    return f"http://127.0.0.1:{mcp_server_port}/mcp"


@pytest.fixture(scope="session")
def mcp_server_process(mcp_server_port: int):
    """
    Check if MCP server is running, skip tests if not.

    To run these tests, start the server first:
        uv run python main.py
    """
    import socket

    # Check if server is already running
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(("127.0.0.1", mcp_server_port))
    sock.close()

    if result != 0:
        pytest.skip(
            f"MCP server not running on port {mcp_server_port}. "
            "Start it with: uv run python main.py"
        )

    yield None


async def send_mcp_request(
    session: aiohttp.ClientSession,
    url: str,
    method: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send a JSON-RPC request to the MCP server."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
    }
    if params:
        payload["params"] = params

    async with session.post(
        url, json=payload, headers={"Content-Type": "application/json"}
    ) as resp:
        resp.raise_for_status()
        return await resp.json()


@pytest.mark.asyncio
async def test_mcp_server_health(mcp_server_url: str, mcp_server_process):
    """Test that the MCP server is running and responding."""
    async with aiohttp.ClientSession() as session:
        # Try to connect to the server
        try:
            async with session.get(mcp_server_url.replace("/mcp", "")) as resp:
                # Server should respond (even if 404, it means it's running)
                assert resp.status in [200, 404, 405]
        except aiohttp.ClientConnectorError:
            pytest.fail("MCP server is not running")


@pytest.mark.asyncio
async def test_mcp_initialize(mcp_server_url: str, mcp_server_process):
    """Test MCP initialize handshake."""
    async with aiohttp.ClientSession() as session:
        response = await send_mcp_request(session, mcp_server_url, "initialize", {})

        assert "jsonrpc" in response
        assert response["jsonrpc"] == "2.0"
        assert "id" in response
        assert "result" in response


@pytest.mark.asyncio
async def test_mcp_list_tools(mcp_server_url: str, mcp_server_process):
    """Test that tools/list returns available tools."""
    async with aiohttp.ClientSession() as session:
        # First initialize
        await send_mcp_request(session, mcp_server_url, "initialize", {})

        # Then list tools
        response = await send_mcp_request(session, mcp_server_url, "tools/list", {})

        assert "result" in response
        assert "tools" in response["result"]
        tools = response["result"]["tools"]

        # Check that expected tools are present
        tool_names = [tool["name"] for tool in tools]
        assert "search_datasets" in tool_names
        assert "create_dataset" in tool_names
        assert "query_dataset_data" in tool_names


@pytest.mark.asyncio
async def test_mcp_search_datasets_tool(mcp_server_url: str, mcp_server_process):
    """Test calling the search_datasets tool."""
    async with aiohttp.ClientSession() as session:
        # Initialize
        await send_mcp_request(session, mcp_server_url, "initialize", {})

        # Call search_datasets tool
        response = await send_mcp_request(
            session,
            mcp_server_url,
            "tools/call",
            {
                "name": "search_datasets",
                "arguments": {"query": "transports", "page_size": 3},
            },
        )

        assert "result" in response
        result = response["result"]
        assert "content" in result
        # Should contain some text about datasets
        assert (
            "transports" in result["content"][0]["text"].lower()
            or "dataset" in result["content"][0]["text"].lower()
        )


@pytest.mark.asyncio
async def test_mcp_tool_invalid_name(mcp_server_url: str, mcp_server_process):
    """Test that calling a non-existent tool returns an error."""
    async with aiohttp.ClientSession() as session:
        # Initialize
        await send_mcp_request(session, mcp_server_url, "initialize", {})

        # Call non-existent tool
        response = await send_mcp_request(
            session,
            mcp_server_url,
            "tools/call",
            {
                "name": "non_existent_tool",
                "arguments": {},
            },
        )

        assert "error" in response
        assert response["error"]["code"] != 0
