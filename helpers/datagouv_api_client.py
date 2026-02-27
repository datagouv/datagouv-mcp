import json
import logging
from typing import Any

import httpx
import yaml

from helpers import env_config

logger = logging.getLogger("datagouv_mcp")


async def _fetch_json(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    logger.debug("datagouv API GET %s", url)
    try:
        resp = await client.get(url, timeout=15.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        logger.error("datagouv API request failed for %s: %s", url, exc)
        raise


def _extract_tags(raw_tags: list[Any]) -> list[str]:
    """Normalize tags to a list of non-empty strings."""
    tags: list[str] = []
    for tag in raw_tags:
        if isinstance(tag, str):
            normalized = tag.strip()
        elif isinstance(tag, dict):
            normalized = str(tag.get("name", "")).strip()
        else:
            continue
        if normalized:
            tags.append(normalized)
    return tags


async def get_resource_details(
    resource_id: str, session: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    """
    Fetch the complete resource payload from the API v2 endpoint.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient()
    assert session is not None
    try:
        base_url: str = env_config.get_base_url("datagouv_api")
        url = f"{base_url}2/datasets/resources/{resource_id}/"
        return await _fetch_json(session, url)
    finally:
        if own:
            await session.aclose()


async def get_resource_metadata(
    resource_id: str, session: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    own = session is None
    if own:
        session = httpx.AsyncClient()
    assert session is not None
    try:
        data = await get_resource_details(resource_id, session=session)
        resource: dict[str, Any] = data.get("resource", {})
        return {
            "id": resource.get("id") or resource_id,
            "title": resource.get("title") or resource.get("name"),
            "description": resource.get("description"),
            "dataset_id": data.get("dataset_id"),
        }
    finally:
        if own:
            await session.aclose()


async def get_dataset_details(
    dataset_id: str, session: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    """
    Fetch the complete dataset payload from the API v1 endpoint.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient()
    assert session is not None
    try:
        base_url: str = env_config.get_base_url("datagouv_api")
        url = f"{base_url}1/datasets/{dataset_id}/"
        return await _fetch_json(session, url)
    finally:
        if own:
            await session.aclose()


async def get_dataset_metadata(
    dataset_id: str, session: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    own = session is None
    if own:
        session = httpx.AsyncClient()
    assert session is not None
    try:
        data = await get_dataset_details(dataset_id, session=session)
        return {
            "id": data.get("id"),
            "title": data.get("title") or data.get("name"),
            "description_short": data.get("description_short"),
            "description": data.get("description"),
        }
    finally:
        if own:
            await session.aclose()


async def get_resource_and_dataset_metadata(
    resource_id: str, session: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    own = session is None
    if own:
        session = httpx.AsyncClient()
    try:
        res: dict[str, Any] = await get_resource_metadata(resource_id, session=session)
        ds: dict[str, Any] = {}
        ds_id = res.get("dataset_id")
        if ds_id:
            ds = await get_dataset_metadata(str(ds_id), session=session)
        return {"resource": res, "dataset": ds}
    finally:
        if own and session:
            await session.aclose()


async def get_resources_for_dataset(
    dataset_id: str, session: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    """
    Get all resources for a given dataset.

    Returns:
        dict with 'dataset' metadata and 'resources' list with key metadata
    """
    own = session is None
    if own:
        session = httpx.AsyncClient()
    assert session is not None
    try:
        data = await get_dataset_details(dataset_id, session=session)
        ds = {
            "id": data.get("id"),
            "title": data.get("title") or data.get("name"),
            "description_short": data.get("description_short"),
            "description": data.get("description"),
        }
        resources: list[dict[str, Any]] = data.get("resources", [])
        res_list: list[dict[str, Any]] = []
        for res in resources:
            resource_id = res.get("id")
            if not resource_id:
                continue
            res_list.append(
                {
                    "id": resource_id,
                    "title": res.get("title", "") or res.get("name", ""),
                    "format": res.get("format"),
                    "filesize": res.get("filesize"),
                    "mime": res.get("mime"),
                    "type": res.get("type"),
                    "url": res.get("url"),
                }
            )
        return {"dataset": ds, "resources": res_list}
    finally:
        if own and session:
            await session.aclose()


async def fetch_openapi_spec(
    url: str, session: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    """
    Fetch and parse an OpenAPI/Swagger spec from a URL.
    Supports both JSON and YAML formats.

    Returns:
        Parsed OpenAPI spec as a dict.

    Raises:
        httpx.HTTPError: If the HTTP request fails.
        ValueError: If the response cannot be parsed as JSON or YAML.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient()
    assert session is not None
    try:
        logger.debug("Fetching OpenAPI spec from %s", url)
        resp = await session.get(url, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
        content = resp.text

        # Try JSON first, then YAML
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass
        try:
            data = yaml.safe_load(content)
            if isinstance(data, dict):
                return data
        except yaml.YAMLError:
            pass

        raise ValueError(f"Could not parse OpenAPI spec from {url} as JSON or YAML")
    finally:
        if own:
            await session.aclose()


async def get_dataservice_details(
    dataservice_id: str, session: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    """
    Fetch the complete dataservice payload from the API v1 endpoint.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient()
    assert session is not None
    try:
        base_url: str = env_config.get_base_url("datagouv_api")
        url = f"{base_url}1/dataservices/{dataservice_id}/"
        return await _fetch_json(session, url)
    finally:
        if own:
            await session.aclose()


async def search_dataservices(
    query: str,
    page: int = 1,
    page_size: int = 20,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Search for dataservices (APIs) on data.gouv.fr.

    Args:
        query: Search query string
        page: Page number (default: 1)
        page_size: Number of results per page (default: 20, max: 100)

    Returns:
        dict with 'data' (list of dataservices), 'page', 'page_size', and 'total'
    """
    own = session is None
    if own:
        session = httpx.AsyncClient()
    assert session is not None
    try:
        base_url: str = env_config.get_base_url("datagouv_api")
        url = f"{base_url}1/dataservices/"
        params = {
            "q": query,
            "page": page,
            "page_size": min(page_size, 100),
        }
        resp = await session.get(url, params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()

        dataservices: list[dict[str, Any]] = data.get("data", [])
        results: list[dict[str, Any]] = []
        for ds in dataservices:
            tags = _extract_tags(ds.get("tags", []))

            results.append(
                {
                    "id": ds.get("id"),
                    "title": ds.get("title") or "",
                    "description": ds.get("description", ""),
                    "organization": ds.get("organization", {}).get("name")
                    if ds.get("organization")
                    else None,
                    "base_api_url": ds.get("base_api_url"),
                    "machine_documentation_url": ds.get("machine_documentation_url"),
                    "tags": tags,
                    "url": f"{env_config.get_base_url('site')}dataservices/{ds.get('id', '')}",
                }
            )

        return {
            "data": results,
            "page": page,
            "page_size": len(results),
            "total": data.get("total", len(results)),
        }
    finally:
        if own:
            await session.aclose()


async def search_datasets(
    query: str,
    page: int = 1,
    page_size: int = 20,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Search for datasets on data.gouv.fr.

    Args:
        query: Search query string (searches in title, description, tags)
        page: Page number (default: 1)
        page_size: Number of results per page (default: 20, max: 100)

    Returns:
        dict with 'data' (list of datasets), 'page', 'page_size', and 'total'
    """
    own = session is None
    if own:
        session = httpx.AsyncClient()
    assert session is not None
    try:
        base_url: str = env_config.get_base_url("datagouv_api")
        # Use API v1 for dataset search
        url = f"{base_url}1/datasets/"
        params = {
            "q": query,
            "page": page,
            "page_size": min(page_size, 100),  # API limit
        }
        resp = await session.get(url, params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()

        datasets: list[dict[str, Any]] = data.get("data", [])
        # Extract relevant fields for each dataset
        results: list[dict[str, Any]] = []
        for ds in datasets:
            tags = _extract_tags(ds.get("tags", []))

            results.append(
                {
                    "id": ds.get("id"),
                    "title": ds.get("title") or ds.get("name", ""),
                    "description": ds.get("description", ""),
                    "description_short": ds.get("description_short", ""),
                    "slug": ds.get("slug", ""),
                    "organization": ds.get("organization", {}).get("name")
                    if ds.get("organization")
                    else None,
                    "tags": tags,
                    "resources_count": len(ds.get("resources", [])),
                    "url": f"{env_config.get_base_url('site')}datasets/{ds.get('slug', ds.get('id', ''))}",
                }
            )

        return {
            "data": results,
            "page": page,
            "page_size": len(results),
            "total": data.get("total", len(results)),
        }
    finally:
        if own:
            await session.aclose()
