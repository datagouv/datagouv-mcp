import logging
from typing import Any

import httpx

from helpers import env_config

logger = logging.getLogger("datagouv_mcp")


async def _get_session(
    session: httpx.AsyncClient | None,
) -> tuple[httpx.AsyncClient, bool]:
    if session is not None:
        return session, False
    new_session = httpx.AsyncClient()
    return new_session, True


async def get_metrics(
    model: str,
    id_value: str,
    *,
    id_field: str | None = None,
    time_granularity: str = "month",
    limit: int = 12,
    sort_order: str = "desc",
    session: httpx.AsyncClient | None = None,
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
        session: Optional httpx session for reuse across calls.

    Returns:
        List of metric records, sorted by the time field in the specified order.
    """
    # Validate and clean id_value
    if not id_value:
        raise ValueError("id_value cannot be empty")
    id_value: str = str(id_value).strip()
    if not id_value:
        raise ValueError("id_value cannot be empty after cleaning")

    if id_field is None:
        # Auto-generate field name: "datasets" -> "dataset_id", "resources" -> "resource_id", etc.
        id_field: str = (
            f"{model.rstrip('s')}_id" if model.endswith("s") else f"{model}_id"
        )

    time_field: str = f"metric_{time_granularity}"
    sess, owns_session = await _get_session(session)
    try:
        base_url: str = env_config.get_base_url("metrics_api")
        url = f"{base_url}{model}/data/"
        params = {
            f"{id_field}__exact": id_value,
            f"{time_field}__sort": sort_order,
            "page_size": max(1, min(limit, 100)),
        }
        logger.debug(
            f"Fetching metrics from {url} with params: {id_field}__exact={id_value}, "
            f"{time_field}__sort={sort_order}, page_size={params['page_size']}"
        )
        resp = await sess.get(url, params=params, timeout=20.0)
        resp.raise_for_status()
        payload = resp.json()
        data: list[dict[str, Any]] = payload.get("data", [])
        logger.debug(f"Received {len(data)} metric entries from API")
        return data
    finally:
        if owns_session:
            await sess.aclose()


async def get_metrics_csv(
    model: str,
    id_value: str,
    *,
    id_field: str | None = None,
    time_granularity: str = "month",
    sort_order: str = "desc",
    session: httpx.AsyncClient | None = None,
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
        session: Optional httpx session for reuse across calls.

    Returns:
        CSV content as a string, including header row.
    """
    # Validate and clean id_value
    if not id_value:
        raise ValueError("id_value cannot be empty")
    id_value: str = str(id_value).strip()
    if not id_value:
        raise ValueError("id_value cannot be empty after cleaning")

    if id_field is None:
        # Auto-generate field name: "datasets" -> "dataset_id", "resources" -> "resource_id", etc.
        id_field: str = (
            f"{model.rstrip('s')}_id" if model.endswith("s") else f"{model}_id"
        )

    time_field: str = f"metric_{time_granularity}"
    sess, owns_session = await _get_session(session)
    try:
        base_url: str = env_config.get_base_url("metrics_api")
        url = f"{base_url}{model}/data/csv/"
        params = {
            f"{id_field}__exact": id_value,
            f"{time_field}__sort": sort_order,
        }
        logger.debug(
            f"Fetching metrics CSV from {url} with params: {id_field}__exact={id_value}, "
            f"{time_field}__sort={sort_order}"
        )
        resp = await sess.get(url, params=params, timeout=30.0)
        resp.raise_for_status()
        return resp.text
    finally:
        if owns_session:
            await sess.aclose()
