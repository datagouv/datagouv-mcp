import logging
from typing import Any

import httpx

from helpers import env_config

logger = logging.getLogger("datagouv_mcp")


class ResourceNotAvailableError(Exception):
    """Raised when a resource is not available via the Tabular API."""


async def _get_session(
    session: httpx.AsyncClient | None,
) -> tuple[httpx.AsyncClient, bool]:
    if session is not None:
        return session, False
    new_session = httpx.AsyncClient()
    return new_session, True


async def fetch_resource_data(
    resource_id: str,
    *,
    page: int = 1,
    page_size: int = 100,
    params: dict[str, Any] | None = None,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Fetch data for a resource via the Tabular API.
    """
    sess, owns_session = await _get_session(session)
    try:
        base_url: str = env_config.get_base_url("tabular_api")
        url = f"{base_url}resources/{resource_id}/data/"
        query_params = {
            "page": max(page, 1),
            "page_size": max(page_size, 1),
        }
        if params:
            query_params.update(params)

        full_url = f"{url}?{'&'.join(f'{k}={v}' for k, v in query_params.items())}"
        logger.info(
            f"Tabular API: Fetching resource data - URL: {full_url}, "
            f"resource_id: {resource_id}"
        )

        resp = await sess.get(url, params=query_params, timeout=30.0)
        if resp.status_code == 404:
            logger.warning(f"Tabular API: Resource {resource_id} not found (404)")
            raise ResourceNotAvailableError(
                f"Resource {resource_id} not available via Tabular API"
            )

        if resp.status_code >= 400:
            error_body = resp.text
            logger.error(
                f"Tabular API: Error {resp.status_code} for resource {resource_id} - "
                f"Response: {error_body[:500]}"
            )

        resp.raise_for_status()
        return resp.json()
    finally:
        if owns_session:
            await sess.aclose()


async def fetch_resource_profile(
    resource_id: str,
    *,
    session: httpx.AsyncClient | None = None,
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
        if resp.status_code == 404:
            logger.warning(
                f"Tabular API: Resource profile {resource_id} not found (404)"
            )
            raise ResourceNotAvailableError(
                f"Resource {resource_id} profile not available via Tabular API"
            )

        if resp.status_code >= 400:
            error_body = resp.text
            logger.error(
                f"Tabular API: Profile error {resp.status_code} for resource {resource_id} - "
                f"Response: {error_body[:500]}"
            )

        resp.raise_for_status()
        return resp.json()
    finally:
        if owns_session:
            await sess.aclose()
