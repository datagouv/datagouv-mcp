"""
Health probe that runs a check on the MCP itself (doing a full handshake)
and calls the `search_datasets` tool with page_size=1 for a full round-trip validation.

Checks if the call response actually contains `data` for valid MCP response

returns True if OK
        False if round-trip failed (meaning the probe failed)
"""

import logging

from mcp.types import TextContent

from helpers.logging import MAIN_LOGGER_NAME
from helpers.mcp_client import call_tool_on_mcp

logger = logging.getLogger(MAIN_LOGGER_NAME)


async def _run_health_check() -> bool:
    logger.debug("health probe: starting health check")
    try:
        result = await call_tool_on_mcp(
            "search_datasets", {"query": "transport", "page_size": 1}
        )
        # result.content is a list of content blocks from the tool response
        # search_datasets always returns a TextContent block
        # we check it's non-empty to confirm a valid round-trip
        if not result.content or not isinstance(result.content[0], TextContent):
            logger.error("health probe: unexpected response from search_datasets")
            return False
        if not result.content[0].text:
            logger.error("health probe: empty response from search_datasets")
            return False

        return True

    except Exception as e:
        logger.error(f"health probe check failed: {e}")
        return False
