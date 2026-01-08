import logging
import time
from typing import Any

import httpx

from helpers import env_config

logger = logging.getLogger("datagouv_mcp")

# Cache for the exceptions list
_exceptions_cache: set[str] | None = None
_cache_timestamp: float = 0
CACHE_TTL_SECONDS: float = 3600.0  # 1 hour


async def _get_session(
    session: httpx.AsyncClient | None,
) -> tuple[httpx.AsyncClient, bool]:
    if session is not None:
        return session, False
    new_session = httpx.AsyncClient()
    return new_session, True


async def fetch_resource_exceptions(
    session: httpx.AsyncClient | None = None,
    force_refresh: bool = False,
) -> set[str]:
    """
    Fetch the list of resource IDs that are exceptions to Tabular API size limits.

    These are resources larger than the normal limits (100 MB for CSV, 12.5 MB for XLSX)
    that are still available via the Tabular API.

    Results are cached for 1 hour to avoid excessive API calls.

    Args:
        session: Optional httpx.AsyncClient to reuse
        force_refresh: If True, bypass the cache and fetch fresh data

    Returns:
        A set of resource IDs that are exceptions
    """
    global _exceptions_cache, _cache_timestamp

    current_time = time.time()

    # Return cached data if valid and not forcing refresh
    if (
        not force_refresh
        and _exceptions_cache is not None
        and (current_time - _cache_timestamp) < CACHE_TTL_SECONDS
    ):
        logger.debug("Using cached exceptions list (%d items)", len(_exceptions_cache))
        return _exceptions_cache

    sess, owns_session = await _get_session(session)
    try:
        base_url: str = env_config.get_base_url("crawler_api")
        url = f"{base_url}resources-exceptions"

        logger.info(f"Crawler API: Fetching resource exceptions from {url}")

        resp = await sess.get(url, timeout=30.0)
        resp.raise_for_status()

        data: list[dict[str, Any]] = resp.json()

        # Extract resource IDs from the response
        # The API returns a list of objects, each containing resource information
        exceptions: set[str] = set()
        for item in data:
            resource_id = item.get("resource_id")
            if resource_id:
                exceptions.add(resource_id)

        # Update cache
        _exceptions_cache = exceptions
        _cache_timestamp = current_time

        logger.info(f"Crawler API: Cached {len(exceptions)} resource exceptions")
        return exceptions

    except httpx.HTTPError as e:
        logger.warning(f"Crawler API: Failed to fetch exceptions: {e}")
        # Return cached data if available, even if stale
        if _exceptions_cache is not None:
            logger.info("Crawler API: Using stale cache due to fetch error")
            return _exceptions_cache
        # Return empty set if no cache available
        return set()
    finally:
        if owns_session:
            await sess.aclose()


async def is_in_exceptions_list(
    resource_id: str,
    session: httpx.AsyncClient | None = None,
) -> bool:
    """
    Check if a resource is in the exceptions list for Tabular API.

    Resources in this list are available via Tabular API despite being larger
    than the normal size limits.

    Args:
        resource_id: The ID of the resource to check
        session: Optional httpx.AsyncClient to reuse

    Returns:
        True if the resource is in the exceptions list, False otherwise
    """
    exceptions = await fetch_resource_exceptions(session=session)
    return resource_id in exceptions


def clear_cache() -> None:
    """Clear the exceptions cache. Useful for testing."""
    global _exceptions_cache, _cache_timestamp
    _exceptions_cache = None
    _cache_timestamp = 0
