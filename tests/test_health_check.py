"""
Health check: full MCP handshake + search_datasets tool call.

Requires a running MCP server (not started by the test).
Excluded from normal pytest runs -- launch explicitly with:

    uv run pytest -m health_check
"""

import pytest

from helpers.health_probe import _run_health_check

pytestmark = pytest.mark.health_check


async def test_health_check():
    """
    Runs the full MCP handshake and calls search_datasets with page_size=1.
    Asserts a valid non-empty response to confirm end-to-end stack is healthy.
    """
    is_healthy = await _run_health_check()
    assert is_healthy, (
        "Health check failed: MCP handshake or tool call returned unexpected result"
    )
