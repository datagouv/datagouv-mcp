import os
from typing import Any

import aiohttp

_ENV_TARGETS = {
    "demo": {
        "api": "https://demo.data.gouv.fr/api/",
        "site": "https://demo.data.gouv.fr/",
        "tabular_api": "https://tabular-api.preprod.data.gouv.fr/api/",
    },
    "prod": {
        "api": "https://www.data.gouv.fr/api/",
        "site": "https://www.data.gouv.fr/",
        "tabular_api": "https://tabular-api.data.gouv.fr/api/",
    },
}


def _normalize_env(value: str | None) -> str:
    if not value:
        return "demo"
    value = value.strip().lower()
    if value in _ENV_TARGETS:
        return value
    return "demo"


def get_current_environment() -> str:
    """
    Return the environment name selected via DATAGOUV_ENV (demo|prod), defaulting to demo.
    """
    return _normalize_env(os.getenv("DATAGOUV_ENV"))


def api_base_url() -> str:
    """
    Return the API base URL for the currently selected environment.
    """
    env_name = get_current_environment()
    return _ENV_TARGETS[env_name]["api"]


def frontend_base_url() -> str:
    """
    Return the public site base URL matching the current environment (demo or prod).
    """
    env_name = get_current_environment()
    return _ENV_TARGETS[env_name]["site"]


def tabular_api_base_url() -> str:
    """
    Return the Tabular API base URL matching the current environment.
    """
    env_name = get_current_environment()
    return _ENV_TARGETS[env_name]["tabular_api"]


def _base_url() -> str:
    return api_base_url()


async def _fetch_json(session: aiohttp.ClientSession, url: str) -> dict[str, Any]:
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
        resp.raise_for_status()
        return await resp.json()


async def get_resource_metadata(
    resource_id: str, session: aiohttp.ClientSession | None = None
) -> dict[str, Any]:
    own = session is None
    if own:
        session = aiohttp.ClientSession()
    assert session is not None
    try:
        # Use API v2 for resources
        url = f"{_base_url()}2/datasets/resources/{resource_id}/"
        data = await _fetch_json(session, url)
        # API v2 returns nested structure
        resource = data.get("resource", {})
        return {
            "id": resource.get("id") or resource_id,
            "title": resource.get("title") or resource.get("name"),
            "description": resource.get("description"),
            "dataset_id": data.get("dataset_id"),
        }
    finally:
        if own:
            await session.close()


async def get_dataset_metadata(
    dataset_id: str, session: aiohttp.ClientSession | None = None
) -> dict[str, Any]:
    own = session is None
    if own:
        session = aiohttp.ClientSession()
    assert session is not None
    try:
        # Use API v1 for datasets
        url = f"{_base_url()}1/datasets/{dataset_id}/"
        data = await _fetch_json(session, url)
        return {
            "id": data.get("id"),
            "title": data.get("title") or data.get("name"),
            "description_short": data.get("description_short"),
            "description": data.get("description"),
        }
    finally:
        if own:
            await session.close()


async def get_resource_and_dataset_metadata(
    resource_id: str, session: aiohttp.ClientSession | None = None
) -> dict[str, Any]:
    own = session is None
    if own:
        session = aiohttp.ClientSession()
    try:
        res: dict[str, Any] = await get_resource_metadata(resource_id, session=session)
        ds: dict[str, Any] = {}
        ds_id = res.get("dataset_id")
        if ds_id:
            ds = await get_dataset_metadata(str(ds_id), session=session)
        return {"resource": res, "dataset": ds}
    finally:
        if own and session:
            await session.close()


async def get_resources_for_dataset(
    dataset_id: str, session: aiohttp.ClientSession | None = None
) -> dict[str, Any]:
    """
    Get all resources for a given dataset.

    Returns:
        dict with 'dataset' metadata and 'resources' list of resource IDs and titles
    """
    own = session is None
    if own:
        session = aiohttp.ClientSession()
    try:
        ds = await get_dataset_metadata(dataset_id, session=session)
        # Fetch resources from API v1
        url = f"{_base_url()}1/datasets/{dataset_id}/"
        data = await _fetch_json(session, url)
        resources = data.get("resources", [])
        res_list = [
            (res.get("id"), res.get("title", "") or res.get("name", ""))
            for res in resources
            if res.get("id")
        ]
        return {"dataset": ds, "resources": res_list}
    finally:
        if own and session:
            await session.close()


async def search_datasets(
    query: str,
    page: int = 1,
    page_size: int = 20,
    session: aiohttp.ClientSession | None = None,
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
        session = aiohttp.ClientSession()
    assert session is not None
    try:
        # Use API v1 for dataset search
        url = f"{_base_url()}1/datasets/"
        params = {
            "q": query,
            "page": page,
            "page_size": min(page_size, 100),  # API limit
        }
        async with session.get(
            url, params=params, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()

        datasets = data.get("data", [])
        # Extract relevant fields for each dataset
        results = []
        for ds in datasets:
            # Handle tags - can be strings or objects with "name" field
            tags = []
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
                    "url": f"{frontend_base_url()}datasets/{ds.get('slug', ds.get('id', ''))}",
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
            await session.close()
