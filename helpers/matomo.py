import logging
import os
from datetime import UTC, datetime

import httpx

from helpers.logging import MAIN_LOGGER_NAME

# Configure Matomo
MATOMO_URL = os.getenv("MATOMO_URL")
MATOMO_SITE_ID = os.getenv("MATOMO_SITE_ID")
MATOMO_AUTH_TOKEN = os.getenv("MATOMO_AUTH")

# Shared client reused across all tracking calls to avoid creating a new
# TCP connection + SSL handshake + httpx overhead on every MCP request.
_client = httpx.AsyncClient(timeout=1.5)


async def track_matomo(url: str, path: str, headers: dict[str, str]) -> None:
    """
    Sends an asynchronous tracking request to Matomo.
    Fired in the background to avoid blocking the MCP server response.
    Skipped when MATOMO_URL or MATOMO_SITE_ID is unset.
    """
    if not MATOMO_URL or not MATOMO_SITE_ID:
        return

    # Extract user-agent for better Matomo analytics
    user_agent: str = headers.get("user-agent", "")

    payload: dict = {
        "idsite": MATOMO_SITE_ID,
        "rec": 1,
        "url": url,
        "action_name": f"MCP Request: {path}",
        "token_auth": MATOMO_AUTH_TOKEN,
        "ua": user_agent,
        "rand": datetime.now(UTC).timestamp(),
    }

    try:
        await _client.post(f"{MATOMO_URL}/matomo.php", data=payload)
    except Exception as e:
        # Fail silently to ensure the MCP server remains operational
        logging.getLogger(MAIN_LOGGER_NAME).error(f"Matomo tracking failed: {e}")
