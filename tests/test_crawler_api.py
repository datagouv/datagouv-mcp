"""Tests for the crawler_api_client helper."""

import pytest

from helpers import crawler_api_client

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    """Clear the exceptions cache before each test."""
    crawler_api_client.clear_cache()


@pytest.mark.asyncio
async def test_fetch_resource_exceptions() -> None:
    """Test that fetch_resource_exceptions returns resource IDs."""
    exceptions = await crawler_api_client.fetch_resource_exceptions()

    assert isinstance(exceptions, set)
    assert len(exceptions) > 0, "Expected at least some resource exceptions"
    for resource_id in exceptions:
        assert isinstance(resource_id, str)


@pytest.mark.asyncio
async def test_is_in_exceptions_list() -> None:
    """Test checking if resources are in the exceptions list."""
    exceptions = await crawler_api_client.fetch_resource_exceptions()

    # A known exception should return True
    if exceptions:
        known_exception = next(iter(exceptions))
        assert await crawler_api_client.is_in_exceptions_list(known_exception) is True

    # A fake resource should return False
    fake_id = "00000000-0000-0000-0000-000000000000"
    assert await crawler_api_client.is_in_exceptions_list(fake_id) is False
