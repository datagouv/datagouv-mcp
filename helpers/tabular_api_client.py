import logging
from typing import Any

import httpx

from helpers import env_config
from helpers.user_agent import USER_AGENT

logger = logging.getLogger("datagouv_mcp")

_client = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})


class ResourceNotAvailableError(Exception):
    """Raised when a resource is not available via the Tabular API."""


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
    client = session or _client
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

    resp = await client.get(url, params=query_params, timeout=30.0)
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


async def fetch_resource_profile(
    resource_id: str,
    *,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Fetch the profile metadata for a resource via the Tabular API.
    """
    client = session or _client
    base_url: str = env_config.get_base_url("tabular_api")
    url = f"{base_url}resources/{resource_id}/profile/"
    logger.debug(
        f"Tabular API: Fetching resource profile - URL: {url}, "
        f"resource_id: {resource_id}"
    )

    resp = await client.get(url, timeout=30.0)
    if resp.status_code == 404:
        logger.warning(f"Tabular API: Resource profile {resource_id} not found (404)")
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
    profile_data: dict[str, Any] = resp.json()

    # Clean up headers: remove surrounding quotes if present
    if "profile" in profile_data and "header" in profile_data["profile"]:
        profile_data["profile"]["header"] = [
            header.strip('"') if isinstance(header, str) else header
            for header in profile_data["profile"]["header"]
        ]

    return profile_data
