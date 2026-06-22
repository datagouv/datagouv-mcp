import json
import logging
from typing import Any

import niquests

from helpers import env_config
from helpers.logging import MAIN_LOGGER_NAME
from helpers.user_agent import USER_AGENT

logger = logging.getLogger(MAIN_LOGGER_NAME)

# User-facing hints (returned to the LLM via tools; keep in English).
MSG_RESOURCE_NOT_IN_TABULAR = (
    "This resource ID was not found in the Tabular API. "
    "Use search_datasets to find a dataset, then list_dataset_resources "
    "to obtain the correct resource ID."
)

MSG_TABULAR_SERVER_ISSUE = (
    "The Tabular API is temporarily unavailable or returned a server error. "
    "Please try again in about one minute."
)

MSG_TABULAR_BAD_REQUEST = (
    "The Tabular API rejected the request (invalid filter, sort column, or parameter). "
    "Call again without sort or filter to preview rows and confirm column names, "
    "or align filter_column and sort_column with the resource schema."
)

MSG_TABULAR_COLUMN_HINT = (
    "A column or parameter in the request does not exist in this resource; "
    "remove sort/filter or use exact names from a preview."
)


class ResourceNotAvailableError(Exception):
    """Raised when a resource is not available via the Tabular API."""


class TabularApiRequestError(Exception):
    """Raised when the Tabular API returns a non-success response (other than 404)."""


def _optional_column_hint(payload: dict[str, Any] | None) -> str | None:
    """If the first Tabular API error looks like a missing column, return a user hint."""
    if payload is None:
        return None
    errors = payload.get("errors")
    if not isinstance(errors, list) or not errors:
        return None
    first = errors[0]
    if not isinstance(first, dict):
        return None
    detail = first.get("detail")
    if isinstance(detail, dict):
        msg = detail.get("message")
        if isinstance(msg, str) and "does not exist" in msg.lower():
            return MSG_TABULAR_COLUMN_HINT
    return None


def _tabular_error_payload_and_messages(
    body: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Parse `body` once (same string as logged); return JSON dict and API detail messages.

    Expects Tabular-style JSON: ``errors[*].detail.message`` strings. Non-JSON bodies
    return ``(None, [])`` so callers can still raise a generic error.
    """
    try:
        data: object = json.loads(body)
    except json.JSONDecodeError:
        return None, []
    if not isinstance(data, dict):
        return None, []

    payload: dict = data
    error_msgs: list[str] = []
    for error in payload["errors"]:
        m = error["detail"]["message"]
        s = m.strip()
        if s:
            error_msgs.append(s)
    return payload, error_msgs


def _raise_for_tabular_failure(
    resp: niquests.Response,
    resource_id: str,
    endpoint: str,
) -> None:
    status = resp.status_code or 0
    body = resp.text or ""
    logger.warning(
        f"Tabular API: HTTP {status} for resource {resource_id} ({endpoint} endpoint)"
    )
    logger.debug(f"Tabular API response body (truncated): {body[:500]}")

    if status >= 500 or status in (408, 429):
        raise TabularApiRequestError(MSG_TABULAR_SERVER_ISSUE)
    if status in (401, 403):
        raise TabularApiRequestError(
            f"The Tabular API returned HTTP {status} (access or permission). "
            "If the problem persists, try again in about one minute."
        )

    payload, error_msgs = _tabular_error_payload_and_messages(body)
    hint = _optional_column_hint(payload)

    msg = MSG_TABULAR_BAD_REQUEST
    if hint:
        msg = f"{msg} {hint}"
    if error_msgs:
        error_msg = ", ".join(error_msgs)
        if len(error_msg) > 2000:
            error_msg = error_msg[:1997] + "..."
        msg = f"{msg} - Original error message: {error_msg}"

    raise TabularApiRequestError(msg)


async def _get_session(
    session: niquests.AsyncSession | None,
) -> tuple[niquests.AsyncSession, bool]:
    if session is not None:
        return session, False
    new_session = niquests.AsyncSession(headers={"User-Agent": USER_AGENT})
    return new_session, True


async def fetch_resource_data(
    resource_id: str,
    *,
    page: int = 1,
    page_size: int = 100,
    params: dict[str, Any] | None = None,
    session: niquests.AsyncSession | None = None,
) -> dict[str, Any]:
    """
    Fetch data for a resource via the Tabular API.
    """
    sess, owns_session = await _get_session(session)
    try:
        base_url: str = env_config.get_base_url("tabular_api")
        url = f"{base_url}resources/{resource_id}/data/"
        query_params: dict[str, str] = {
            "page": str(max(page, 1)),
            "page_size": str(max(page_size, 1)),
        }
        if params:
            query_params.update({k: str(v) for k, v in params.items()})

        full_url = f"{url}?{'&'.join(f'{k}={v}' for k, v in query_params.items())}"
        logger.info(
            f"Tabular API: Fetching resource data - URL: {full_url}, "
            f"resource_id: {resource_id}"
        )

        resp = await sess.get(url, params=query_params, timeout=30.0)
        status_code = resp.status_code
        if status_code == 404:
            logger.warning(f"Tabular API: Resource {resource_id} not found (404)")
            raise ResourceNotAvailableError(MSG_RESOURCE_NOT_IN_TABULAR)

        if status_code is not None and status_code >= 400:
            _raise_for_tabular_failure(resp, resource_id, endpoint="data")

        return resp.json()
    finally:
        if owns_session:
            await sess.close()


async def fetch_resource_profile(
    resource_id: str,
    *,
    session: niquests.AsyncSession | None = None,
) -> dict[str, Any]:
    """
    Fetch the profile metadata for a resource via the Tabular API.
    """

    sess, owns_session = await _get_session(session)
    try:
        base_url: str = env_config.get_base_url("tabular_api")
        url = f"{base_url}resources/{resource_id}/profile/"
        logger.debug(
            f"Tabular API: Fetching resource profile - URL: {url}, "
            f"resource_id: {resource_id}"
        )

        resp = await sess.get(url, timeout=30.0)
        status_code = resp.status_code
        if status_code == 404:
            logger.warning(
                f"Tabular API: Resource profile {resource_id} not found (404)"
            )
            raise ResourceNotAvailableError(MSG_RESOURCE_NOT_IN_TABULAR)

        if status_code is not None and status_code >= 400:
            _raise_for_tabular_failure(resp, resource_id, endpoint="profile")

        profile_data: dict[str, Any] = resp.json()

        # Clean up headers: remove surrounding quotes if present
        if "profile" in profile_data and "header" in profile_data["profile"]:
            profile_data["profile"]["header"] = [
                header.strip('"') if isinstance(header, str) else header
                for header in profile_data["profile"]["header"]
            ]

        return profile_data
    finally:
        if owns_session:
            await sess.close()
