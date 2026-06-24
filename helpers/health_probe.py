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

logger = logging.getLogger(MAIN_LOGGER_NAME)


async def _run_health_check(mcp: FastMCP) -> bool:
    logger.debug("health probe: starting health check")
    try:
        content, _ = await mcp.call_tool(
            "search_datasets",
            {"query": "transport", "page_size": 1},
        )
        # search_datasets always returns a TextContent block
        # we check it's non-empty to confirm a valid round-trip
        if not content or not isinstance(content[0], TextContent):
            logger.error("health probe: unexpected response from search_datasets")
            return False
        if not content[0].text:
            logger.error("health probe: empty response from search_datasets")
            return False

        return True

    except Exception as e:
        logger.error(f"health probe check failed: {e}")
        return False
