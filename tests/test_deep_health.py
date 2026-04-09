"""
Deep health check: full MCP handshake + search_datasets tool call.

Requires a running MCP server (not started by the test).
Excluded from normal pytest runs -- launch explicitly with:

    uv run pytest -m deep_health
"""

import pytest

from helpers.health_probe import _run_deep_check

pytestmark = pytest.mark.deep_health


async def test_deep_health():
    """
    Runs the full MCP handshake and calls search_datasets with page_size=1.
    Asserts a valid non-empty response to confirm end-to-end stack is healthy.
    """
    is_healthy = await _run_deep_check()
    assert is_healthy, (
        "Deep health check failed: MCP handshake or tool call returned unexpected result"
    )
