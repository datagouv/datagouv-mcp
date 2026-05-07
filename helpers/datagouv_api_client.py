import json
import logging
from typing import Any

import httpx
import yaml

from helpers import env_config
from helpers.logging import MAIN_LOGGER_NAME
from helpers.user_agent import USER_AGENT

logger = logging.getLogger(MAIN_LOGGER_NAME)


async def _fetch_json(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    logger.debug("datagouv API GET %s", url)
    try:
        resp = await client.get(url, timeout=15.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        logger.error("datagouv API request failed for %s: %s", url, exc)
        raise


async def get_resource_details(
    resource_id: str, session: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    """
    Fetch the complete resource payload from the API v2 endpoint.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
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
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
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
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
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
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
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
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
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
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    try:
        ds = await get_dataset_metadata(dataset_id, session=session)
        base_url: str = env_config.get_base_url("datagouv_api")
        # Fetch resources from API v1
        url = f"{base_url}1/datasets/{dataset_id}/"
        data = await _fetch_json(session, url)  # type: ignore
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
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        logger.debug("Fetching OpenAPI spec from %s", url)
        resp = await session.get(url, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
        content = resp.text

        # Try JSON first, then YAML
        try:
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            pass
        try:
            return yaml.safe_load(content)
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
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
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
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        base_url: str = env_config.get_base_url("datagouv_api")
        url = f"{base_url}2/dataservices/search/"
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
            tags: list[str] = ds.get("tags") or []

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
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        base_url: str = env_config.get_base_url("datagouv_api")
        # Use API v2 for dataset search
        url = f"{base_url}2/datasets/search/"
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
            tags: list[str] = ds.get("tags") or []

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


def _organization_metrics_summary(metrics: Any) -> dict[str, Any] | None:
    """Pick a small subset of organization metrics for tool responses."""
    if not isinstance(metrics, dict):
        return None
    keys = ("datasets", "reuses", "followers", "views")
    out: dict[str, Any] = {}
    for k in keys:
        if k in metrics and metrics[k] is not None:
            out[k] = metrics[k]
    return out or None


async def search_organizations(
    query: str = "",
    page: int = 1,
    page_size: int = 20,
    sort: str | None = None,
    badge: str | None = None,
    name: str | None = None,
    business_number_id: str | None = None,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    List or search publishing organizations on data.gouv.fr.

    Args:
        query: Optional search string; keyword-style search over organization fields.
        page: Page number (default: 1).
        page_size: Results per page (default: 20, max: 100).
        sort: Sort field, optionally prefixed with '-' for descending. Examples: name,
            datasets, reuses, followers, views, created, last_modified, and -datasets.
        badge: Filter by badge kind: public-service, certified, association, company,
            local-authority.
        name: Filter by exact organization name.
        business_number_id: Filter by SIREN or other business id when indexed.

    Returns:
        dict with keys: 'data' (list of trimmed org dicts: id, name, slug, acronym,
        badges, metrics, profile_url, url), 'page', 'page_size', and 'total' (full
        match count across pages).
    """
    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        base_url: str = env_config.get_base_url("datagouv_api")
        url = f"{base_url}2/organizations/search/"
        params: dict[str, Any] = {
            "page": page,
            "page_size": min(page_size, 100),
        }
        if query:
            params["q"] = query
        if sort:
            params["sort"] = sort
        if badge:
            params["badge"] = badge
        if name:
            params["name"] = name
        if business_number_id:
            params["business_number_id"] = business_number_id

        resp = await session.get(url, params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()

        orgs: list[dict[str, Any]] = data.get("data", [])
        site_base = env_config.get_base_url("site").rstrip("/")
        results: list[dict[str, Any]] = []
        for org in orgs:
            raw_badges = org.get("badges") or []
            badge_kinds: list[str] = []
            for b in raw_badges:
                if isinstance(b, dict) and b.get("kind"):
                    badge_kinds.append(str(b["kind"]))

            metrics_summary = _organization_metrics_summary(org.get("metrics"))

            slug = org.get("slug") or ""
            org_id = org.get("id")
            results.append(
                {
                    "id": org_id,
                    "name": org.get("name") or "",
                    "slug": slug,
                    "acronym": org.get("acronym"),
                    "badges": badge_kinds,
                    "metrics": metrics_summary,
                    "profile_url": org.get("page"),
                    "url": f"{site_base}/organizations/{slug or org_id or ''}",
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
