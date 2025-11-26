import os
from typing import Any

import aiohttp

_METRIC_API_BASE_URLS = {
    # Official public endpoint
    # Note: There is no demo/preprod environment for the Metric API.
    # This structure is kept for future merging with _ENV_TARGETS.
    "prod": "https://metric-api.data.gouv.fr/api/",
}


def metric_api_base_url() -> str:
    """
    Return the Metric API base URL.
    The Metric API only has a production endpoint (no demo/preprod).
    A METRIC_API_BASE_URL env var can override the default.
    """
    custom = os.getenv("METRIC_API_BASE_URL")
    if custom:
        return custom.rstrip("/") + "/"

    # Always use prod since there's no demo/preprod for Metric API
    return _METRIC_API_BASE_URLS["prod"]


async def _get_session(
    session: aiohttp.ClientSession | None,
) -> tuple[aiohttp.ClientSession, bool]:
    if session is not None:
        return session, False
    new_session = aiohttp.ClientSession()
    return new_session, True


async def get_metrics(
    model: str,
    id_value: str,
    *,
    id_field: str | None = None,
    time_granularity: str = "month",
    limit: int = 12,
    sort_order: str = "desc",
    session: aiohttp.ClientSession | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch metrics for a given model and ID with specified time granularity.

    Args:
        model: Metric model name (e.g. "datasets", "resources", "organizations", "reuses").
        id_value: The ID value to filter by (e.g. dataset_id, resource_id, organization_id, reuse_id).
        id_field: The ID field name (defaults to "{model}_id", e.g. "dataset_id" for model "datasets").
        time_granularity: Time granularity for metrics (default: "month"). Currently only "month" is
            supported by the API, but this parameter allows for future extensibility (e.g. "day", "week", "year").
        limit: Maximum number of records to return (default: 12, max: 100).
        sort_order: Sort order for time field ("asc" or "desc", default: "desc").
        session: Optional aiohttp session for reuse across calls.

    Returns:
        List of metric records, sorted by the time field in the specified order.
    """
    if id_field is None:
        # Auto-generate field name: "datasets" -> "dataset_id", "resources" -> "resource_id", etc.
        id_field = f"{model.rstrip('s')}_id" if model.endswith("s") else f"{model}_id"

    time_field = f"metric_{time_granularity}"
    sess, owns_session = await _get_session(session)
    try:
        base_url = metric_api_base_url()
        url = f"{base_url}{model}/data/"
        params = {
            f"{id_field}__exact": id_value,
            f"{time_field}__sort": sort_order,
            "page_size": max(1, min(limit, 100)),
        }
        async with sess.get(
            url,
            params=params,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            resp.raise_for_status()
            payload = await resp.json()
            return payload.get("data", [])
    finally:
        if owns_session:
            await sess.close()


async def get_metrics_csv(
    model: str,
    id_value: str,
    *,
    id_field: str | None = None,
    time_granularity: str = "month",
    sort_order: str = "desc",
    session: aiohttp.ClientSession | None = None,
) -> str:
    """
    Fetch metrics as CSV for a given model and ID with specified time granularity.

    Note: The CSV endpoint may return all matching records regardless of pagination parameters.
    Use filters to limit the result set if needed.

    Args:
        model: Metric model name (e.g. "datasets", "resources", "organizations", "reuses").
        id_value: The ID value to filter by (e.g. dataset_id, resource_id, organization_id, reuse_id).
        id_field: The ID field name (defaults to "{model}_id", e.g. "dataset_id" for model "datasets").
        time_granularity: Time granularity for metrics (default: "month"). Currently only "month" is
            supported by the API, but this parameter allows for future extensibility (e.g. "day", "week", "year").
        sort_order: Sort order for time field ("asc" or "desc", default: "desc").
        session: Optional aiohttp session for reuse across calls.

    Returns:
        CSV content as a string, including header row.
    """
    if id_field is None:
        # Auto-generate field name: "datasets" -> "dataset_id", "resources" -> "resource_id", etc.
        id_field = f"{model.rstrip('s')}_id" if model.endswith("s") else f"{model}_id"

    time_field = f"metric_{time_granularity}"
    sess, owns_session = await _get_session(session)
    try:
        base_url = metric_api_base_url()
        url = f"{base_url}{model}/data/csv/"
        params = {
            f"{id_field}__exact": id_value,
            f"{time_field}__sort": sort_order,
        }
        async with sess.get(
            url,
            params=params,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            resp.raise_for_status()
            return await resp.text()
    finally:
        if owns_session:
            await sess.close()
