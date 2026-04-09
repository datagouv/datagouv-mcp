import logging
import os
from contextvars import ContextVar, Token
from datetime import UTC, datetime

import httpx

from helpers.logging import MAIN_LOGGER_NAME

# Configure Matomo
MATOMO_URL = os.getenv("MATOMO_URL")
MATOMO_SITE_ID = os.getenv("MATOMO_SITE_ID")
MATOMO_AUTH_TOKEN = os.getenv("MATOMO_AUTH_TOKEN")
MATOMO_TOOL_EVENT_CATEGORY = "MCP"

_request_page_url: ContextVar[str] = ContextVar(
    "matomo_request_page_url", default="https://localhost/mcp"
)
_request_user_agent: ContextVar[str] = ContextVar(
    "matomo_request_user_agent", default=""
)

# Shared client reused across all tracking calls to avoid creating a new
# TCP connection + SSL handshake + httpx overhead on every MCP request.
_client = httpx.AsyncClient(timeout=1.5)


def apply_matomo_request_context(
    headers: dict[str, str], path: str
) -> tuple[Token[str], Token[str]]:
    """Bind URL and User-Agent for the current HTTP request (for tool event tracking)."""
    host = headers.get("host", "localhost")
    full_url = f"https://{host}{path}"
    return (
        _request_page_url.set(full_url),
        _request_user_agent.set(headers.get("user-agent", "")),
    )


def reset_matomo_request_context(
    url_token: Token[str],
    ua_token: Token[str],
) -> None:
    _request_page_url.reset(url_token)
    _request_user_agent.reset(ua_token)


async def _post_matomo(payload: dict) -> None:
    """POST tracking payload to Matomo; no-op when tracking is disabled."""
    if not MATOMO_URL or not MATOMO_SITE_ID:
        return
    try:
        await _client.post(f"{MATOMO_URL}/matomo.php", data=payload)
    except Exception as e:
        logging.getLogger(MAIN_LOGGER_NAME).error(f"Matomo tracking failed: {e}")


async def track_matomo_request(url: str, path: str, headers: dict[str, str]) -> None:
    """Track one HTTP-level MCP request (page-action style)."""
    user_agent = headers.get("user-agent", "")
    payload = {
        "idsite": MATOMO_SITE_ID,
        "rec": 1,
        "url": url,
        "action_name": f"MCP Request: {path}",
        "token_auth": MATOMO_AUTH_TOKEN,
        "ua": user_agent,
        "rand": datetime.now(UTC).timestamp(),
    }
    await _post_matomo(payload)


async def track_matomo_tool(tool_name: str) -> None:
    """
    Track an MCP tool invocation as a Matomo event (Behavior > Events).
    Uses e_c / e_a and ca=1 per the HTTP Tracking API.
    """
    payload = {
        "idsite": MATOMO_SITE_ID,
        "rec": 1,
        "url": _request_page_url.get(),
        "ca": 1,
        "e_c": MATOMO_TOOL_EVENT_CATEGORY,
        "e_a": tool_name,
        "token_auth": MATOMO_AUTH_TOKEN,
        "ua": _request_user_agent.get(),
        "rand": datetime.now(UTC).timestamp(),
    }
    await _post_matomo(payload)
