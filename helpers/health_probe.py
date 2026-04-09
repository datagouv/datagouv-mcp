"""
Health probe that runs a deep check on the MCP itself (doing a full handshake)
and calls the `search_datasets` tool with page_size=1 for a full round-trip validation.

Checks if the call response actually contains `data` for valid MCP response

returns True if OK
        False if round-trip failed (meaning the probe failed)
"""

import logging
import os

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import TextContent

from helpers.logging import MAIN_LOGGER_NAME

logger = logging.getLogger(MAIN_LOGGER_NAME)


async def _run_deep_check() -> bool:
    logger.debug("health probe: starting deep check")
    try:
        port = os.getenv("MCP_PORT", "8000")
        url = f"http://localhost:{port}/mcp"

        async with streamable_http_client(url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "search_datasets", {"query": "transport", "page_size": 1}
                )
                # result.content is a list of content blocks from the tool response
                # search_datasets always returns a TextContent block
                # we check it's non-empty to confirm a valid round-trip
                if not result.content or not isinstance(result.content[0], TextContent):
                    logger.error(
                        "health probe: unexpected response from search_datasets"
                    )
                    return False
                if not result.content[0].text:
                    logger.error("health probe: empty response from search_datasets")
                    return False

        return True

    except Exception as e:
        logger.error("health probe: deep check failed: %s", e)
        return False
