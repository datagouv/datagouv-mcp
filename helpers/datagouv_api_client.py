from typing import Any

import httpx

from helpers import env_config


async def _fetch_json(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    resp = await client.get(url, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


async def get_resource_metadata(
    resource_id: str, session: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    own = session is None
    if own:
        session = httpx.AsyncClient()
    assert session is not None
    try:
        base_url: str = env_config.get_base_url("datagouv_api")
        # Use API v2 for resources
        url = f"{base_url}2/datasets/resources/{resource_id}/"
        data = await _fetch_json(session, url)
        # API v2 returns nested structure
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


async def get_dataset_metadata(
    dataset_id: str, session: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    own = session is None
    if own:
        session = httpx.AsyncClient()
    assert session is not None
    try:
        base_url: str = env_config.get_base_url("datagouv_api")
        # Use API v1 for datasets
        url = f"{base_url}1/datasets/{dataset_id}/"
        data = await _fetch_json(session, url)
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
        dict with 'dataset' metadata and 'resources' list of resource IDs and titles
    """
    own = session is None
    if own:
        session = httpx.AsyncClient()
    try:
        ds = await get_dataset_metadata(dataset_id, session=session)
        base_url: str = env_config.get_base_url("datagouv_api")
        # Fetch resources from API v1
        url = f"{base_url}1/datasets/{dataset_id}/"
        data = await _fetch_json(session, url)
        resources: list[dict[str, Any]] = data.get("resources", [])
        res_list: list[tuple[str, str]] = [
            (res.get("id"), res.get("title", "") or res.get("name", ""))
            for res in resources
            if res.get("id")
        ]
        return {"dataset": ds, "resources": res_list}
    finally:
        if own and session:
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
            # Handle tags - can be strings or objects with "name" field
            tags: list[str] = []
            for tag in ds.get("tags", []):
                if isinstance(tag, str):
                    tags.append(tag)
                elif isinstance(tag, dict):
                    tags.append(tag.get("name", ""))

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
