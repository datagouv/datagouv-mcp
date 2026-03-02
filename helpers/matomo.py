import logging
import os
from datetime import UTC, datetime

import httpx

# Configure Matomo
MATOMO_URL = "https://stats.data.gouv.fr"
MATOMO_SITE_ID = os.getenv("MATOMO_SITE_ID")
MATOMO_AUTH_TOKEN = os.getenv("MATOMO_AUTH")


async def track_matomo(url: str, path: str, headers: dict[str, str]) -> None:
    """
    Sends an asynchronous tracking request to Matomo.
    Fired in the background to avoid blocking the MCP server response.
    """
    if not MATOMO_SITE_ID:
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
        # Using a context manager for the client; timeout is short to prevent hanging
        async with httpx.AsyncClient() as client:
            await client.post(f"{MATOMO_URL}/matomo.php", data=payload, timeout=1.5)
    except Exception as e:
        # Fail silently to ensure the MCP server remains operational
        logging.getLogger("datagouv_mcp").error(f"Matomo tracking failed: {e}")
