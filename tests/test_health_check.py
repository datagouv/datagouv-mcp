"""
Health check: in-process search_datasets tool call.

Calls the tool layer directly (no HTTP round-trip to localhost/mcp).
Requires network access to data.gouv.fr. Excluded from normal pytest runs:

    uv run pytest -m health_check
"""

import pytest

from helpers.health_probe import _run_health_check
from main import mcp

pytestmark = pytest.mark.health_check


async def test_health_check():
    """
    Calls search_datasets with page_size=1 in-process.
    Asserts a valid non-empty response to confirm end-to-end stack is healthy.
    """
    is_healthy = await _run_health_check(mcp)
    assert is_healthy, "Health check failed: tool call returned unexpected result"
