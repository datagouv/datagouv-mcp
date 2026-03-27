"""
Stress tests: send many concurrent MCP requests against a running server.

Requires a running MCP server (not started by the test).
Excluded from normal pytest runs -- launch explicitly with:

    uv run pytest -m stress
"""

import asyncio
import json
import os
import random
import string
from urllib.parse import urlparse

import pytest

MCP_PORT = os.getenv("MCP_PORT", "8000")
MCP_URL = f"http://localhost:{MCP_PORT}/mcp"
NUM_REQUESTS = 100
MAX_CONCURRENT = 20

TOOL_NAME = "search_datasets"
QUERIES = ["transport", "education", "sante", "energie", "elections"]

pytestmark = pytest.mark.stress


def _build_raw_http_request(tool_name: str, tool_args: dict) -> bytes:
    request_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=16))
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": tool_args},
        }
    )
    parsed = urlparse(MCP_URL)
    host = parsed.hostname
    port = parsed.port or 80
    raw = (
        f"POST {parsed.path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Content-Type: application/json\r\n"
        f"Accept: text/event-stream, application/json\r\n"
        f"Content-Length: {len(payload)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
        f"{payload}"
    )
    return raw.encode()


async def _fire_and_read(tool_name: str, tool_args: dict) -> str:
    """Send request and fully read the response (normal flow)."""
    parsed = urlparse(MCP_URL)
    host = parsed.hostname or "localhost"
    port = parsed.port or 80
    raw_request = _build_raw_http_request(tool_name, tool_args)
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(raw_request)
    await writer.drain()
    response = await asyncio.wait_for(reader.read(65536), timeout=30.0)
    writer.close()
    await writer.wait_closed()
    assert response, "Empty response from server"
    assert b"200 OK" in response
    return "success"


async def _fire_and_disconnect(tool_name: str, tool_args: dict) -> str:
    """Send request then close TCP socket immediately -- don't read response."""
    parsed = urlparse(MCP_URL)
    host = parsed.hostname or "localhost"
    port = parsed.port or 80
    raw_request = _build_raw_http_request(tool_name, tool_args)
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(raw_request)
    await writer.drain()
    writer.close()
    await writer.wait_closed()
    return "cut"


async def _worker(
    sem: asyncio.Semaphore, tool_name: str, tool_args: dict, cut: bool
) -> str:
    async with sem:
        if cut:
            return await _fire_and_disconnect(tool_name, tool_args)
        return await _fire_and_read(tool_name, tool_args)


async def test_server_handles_abrupt_disconnects():
    """
    Send NUM_REQUESTS concurrent requests, half of which cut the TCP
    connection immediately. The server must not crash and must continue
    to serve the normal requests successfully.
    """
    sem = asyncio.Semaphore(MAX_CONCURRENT)

    tasks = []
    for i in range(NUM_REQUESTS):
        args = {"query": QUERIES[i % len(QUERIES)], "page": 1, "page_size": 5}
        cut = i % 2 == 0
        tasks.append(_worker(sem, TOOL_NAME, args, cut))

    results = await asyncio.gather(*tasks)

    cuts = [r for r in results if r == "cut"]
    successes = [r for r in results if r == "success"]

    assert len(cuts) == NUM_REQUESTS // 2, (
        f"Expected {NUM_REQUESTS // 2} cut requests, got {len(cuts)}"
    )
    assert len(successes) == NUM_REQUESTS - NUM_REQUESTS // 2, (
        f"Expected {NUM_REQUESTS - NUM_REQUESTS // 2} successful requests, got {len(successes)}"
    )
