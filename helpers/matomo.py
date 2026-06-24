import logging
import os
import random
from contextvars import ContextVar, Token

import niquests

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
_request_cip: ContextVar[str] = ContextVar("matomo_request_cip", default="")

_matomo_tool_event_action: ContextVar[str | None] = ContextVar(
    "matomo_tool_event_action", default=None
)

# Shared client reused across all tracking calls to avoid creating a new
# TCP connection + SSL handshake + HTTP client overhead on every MCP request.
_client = niquests.AsyncSession(timeout=1.5)


def apply_matomo_request_context(
    headers: dict[str, str], path: str
) -> tuple[Token[str], Token[str], Token[str]]:
    """Bind URL, User-Agent, and client IP for the current HTTP request (for tool event tracking)."""
    host = headers.get("host", "localhost")
    full_url = f"https://{host}{path}"
    cip = headers.get("x-forwarded-for", "").split(",")[0].strip()
    return (
        _request_page_url.set(full_url),
        _request_user_agent.set(headers.get("user-agent", "")),
        _request_cip.set(cip),
    )


def reset_matomo_request_context(
    url_token: Token[str],
    ua_token: Token[str],
    cip_token: Token[str],
) -> None:
    _request_page_url.reset(url_token)
    _request_user_agent.reset(ua_token)
    _request_cip.reset(cip_token)


def apply_matomo_tool_event_action(action: str) -> Token[str | None]:
    """Override Matomo e_a for tool call(s) in this async context."""
    return _matomo_tool_event_action.set(action)


def reset_matomo_tool_event_action(token: Token[str | None]) -> None:
    _matomo_tool_event_action.reset(token)


def matomo_tool_event_for(tool_name: str) -> str:
    """Return Matomo event action for a tool call (override or tool name)."""
    return _matomo_tool_event_action.get() or tool_name


async def _post_matomo(payload: dict) -> None:
    """POST tracking payload to Matomo; no-op when tracking is disabled."""
    if not MATOMO_URL or not MATOMO_SITE_ID:
        return
    try:
        resp = await _client.post(f"{MATOMO_URL}/matomo.php", data=payload)
        resp.raise_for_status()
    except Exception as e:
        logging.getLogger(MAIN_LOGGER_NAME).error(
            f"Matomo tracking failed: {e}", exc_info=True
        )


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
        "ua": _request_user_agent.get(),
        "rand": str(random.randint(10**15, 10**16 - 1)),
    }
    if MATOMO_AUTH_TOKEN:
        payload["token_auth"] = MATOMO_AUTH_TOKEN
        cip = _request_cip.get()
        if cip:
            payload["cip"] = cip
    await _post_matomo(payload)
