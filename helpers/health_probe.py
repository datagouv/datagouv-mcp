"""
Health probe that validates MCP tool execution in-process.

Calls `search_datasets` with page_size=1 to confirm the tool layer and
data.gouv.fr API access work end-to-end, without a recursive HTTP round-trip.

Returns True if OK, False if the probe failed.
"""

import logging

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent

from helpers.logging import MAIN_LOGGER_NAME
from helpers.matomo import (
    apply_matomo_tool_event_action,
    reset_matomo_tool_event_action,
)

logger = logging.getLogger(MAIN_LOGGER_NAME)


async def _run_health_check(mcp: FastMCP) -> bool:
    logger.debug("health probe: starting health check")
    try:
        action_token = apply_matomo_tool_event_action("health_check")
        try:
            content, _ = await mcp.call_tool(
                "search_datasets",
                {"query": "transport", "page_size": 1},
            )
        finally:
            reset_matomo_tool_event_action(action_token)
        # search_datasets always returns a TextContent block
        if not content or not isinstance(content[0], TextContent):  # type: ignore
            logger.error("health probe: unexpected response from search_datasets")
            return False
        if not content[0].text:  # type: ignore
            logger.error("health probe: empty response from search_datasets")
            return False

        return True

    except Exception as e:
        logger.error(f"health probe check failed: {e}")
        return False
