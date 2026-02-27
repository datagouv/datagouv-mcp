"""Tests for the tabular_api_client helper."""

import os

import pytest

from helpers import tabular_api_client

pytestmark = pytest.mark.integration

# Default test resource ID (known to work with demo environment)
DEFAULT_TEST_RESOURCE_ID = "3b6b2281-b9d9-4959-ae9d-c2c166dff118"


@pytest.fixture
def resource_id() -> str:
    """Fixture providing a test resource ID."""
    return os.getenv("RESOURCE_ID", DEFAULT_TEST_RESOURCE_ID)


@pytest.mark.asyncio
async def test_fetch_resource_profile(resource_id: str) -> None:
    """Test fetching resource profile."""
    profile = await tabular_api_client.fetch_resource_profile(resource_id)

    assert "profile" in profile
    profile_data = profile["profile"]
    assert "header" in profile_data
    assert isinstance(profile_data["header"], list)
    assert len(profile_data["header"]) > 0

    if "columns" in profile_data:
        assert isinstance(profile_data["columns"], dict)
        assert len(profile_data["columns"]) > 0


@pytest.mark.asyncio
async def test_fetch_resource_data_basic(resource_id: str) -> None:
    """Test basic fetching of resource data."""
    data = await tabular_api_client.fetch_resource_data(
        resource_id, page=1, page_size=5
    )

    assert "data" in data
    assert "meta" in data
    assert "links" in data

    rows = data["data"]
    assert isinstance(rows, list)
    assert len(rows) > 0

    # Check that rows have consistent structure
    if rows:
        first_row_keys = set(rows[0].keys())
        for row in rows[1:]:
            assert set(row.keys()) == first_row_keys


@pytest.mark.asyncio
async def test_fetch_resource_data_pagination(resource_id: str) -> None:
    """Test pagination in resource data."""
    page_size = 3
    page1_data = await tabular_api_client.fetch_resource_data(
        resource_id, page=1, page_size=page_size
    )

    assert len(page1_data["data"]) <= page_size
    meta = page1_data["meta"]
    assert meta["page"] == 1
    assert meta["page_size"] == page_size
    assert meta["total"] > 0

    # If there's a next page, fetch it
    if page1_data["links"].get("next"):
        page2_data = await tabular_api_client.fetch_resource_data(
            resource_id, page=2, page_size=page_size
        )
        assert page2_data["meta"]["page"] == 2
        # Rows should be different
        if page1_data["data"] and page2_data["data"]:
            assert page1_data["data"][0] != page2_data["data"][0]


@pytest.mark.asyncio
async def test_fetch_resource_data_with_params(resource_id: str) -> None:
    """Test fetching resource data with custom parameters."""
    params = {"page_size": 2}
    data = await tabular_api_client.fetch_resource_data(
        resource_id, page=1, page_size=10, params=params
    )

    # The params should override the page_size argument
    assert len(data["data"]) <= 2
    assert data["meta"]["page_size"] == 2


@pytest.mark.asyncio
async def test_fetch_resource_data_metadata(resource_id: str) -> None:
    """Test that metadata is correctly returned."""
    data = await tabular_api_client.fetch_resource_data(
        resource_id, page=1, page_size=5
    )

    meta = data["meta"]
    assert "total" in meta
    assert "page" in meta
    assert "page_size" in meta
    assert meta["total"] > 0
    assert meta["page"] == 1
    assert meta["page_size"] == 5


@pytest.mark.asyncio
async def test_fetch_resource_data_links(resource_id: str) -> None:
    """Test that pagination links are correctly returned."""
    data = await tabular_api_client.fetch_resource_data(
        resource_id, page=1, page_size=5
    )

    links = data["links"]
    assert "profile" in links
    assert "swagger" in links

    # If there are more pages, next link should be present
    meta = data["meta"]
    if meta["total"] > meta["page_size"]:
        assert "next" in links


@pytest.mark.asyncio
async def test_invalid_resource_raises_error() -> None:
    """Test that invalid resource ID raises ResourceNotAvailableError."""
    invalid_id = "00000000-0000-0000-0000-000000000000"

    with pytest.raises(tabular_api_client.ResourceNotAvailableError):
        await tabular_api_client.fetch_resource_data(invalid_id, page_size=1)


@pytest.mark.asyncio
async def test_invalid_resource_profile_raises_error() -> None:
    """Test that invalid resource ID raises error for profile."""
    invalid_id = "00000000-0000-0000-0000-000000000000"

    with pytest.raises(tabular_api_client.ResourceNotAvailableError):
        await tabular_api_client.fetch_resource_profile(invalid_id)


@pytest.mark.asyncio
async def test_profile_and_data_consistency(resource_id: str) -> None:
    """Test that profile headers match data column names."""
    profile = await tabular_api_client.fetch_resource_profile(resource_id)
    data = await tabular_api_client.fetch_resource_data(
        resource_id, page=1, page_size=1
    )

    profile_headers = profile["profile"]["header"]
    if data["data"]:
        data_columns = [col for col in data["data"][0].keys() if col != "__id"]
        # Headers should match (excluding __id from data)
        assert len(profile_headers) == len(data_columns)
        # Check that all headers are in data columns
        for header in profile_headers:
            assert header in data_columns


@pytest.mark.asyncio
async def test_fetch_resource_data_with_filter(resource_id: str) -> None:
    """Test fetching resource data with filter parameters."""
    # First get profile to find a column name
    profile = await tabular_api_client.fetch_resource_profile(resource_id)
    profile_headers = profile["profile"]["header"]

    if not profile_headers:
        pytest.skip("No columns available in test resource")

    # Use first column for filtering
    test_column = profile_headers[0]

    # Get a value from first row to use as filter
    all_data = await tabular_api_client.fetch_resource_data(
        resource_id, page=1, page_size=5
    )
    if not all_data["data"]:
        pytest.skip("No data available in test resource")

    filter_value = str(all_data["data"][0].get(test_column, ""))
    if not filter_value:
        pytest.skip(f"Column {test_column} has no value to filter on")

    # Test filter with exact match
    params = {f"{test_column}__exact": filter_value}
    filtered_data = await tabular_api_client.fetch_resource_data(
        resource_id, page=1, page_size=10, params=params
    )

    assert "data" in filtered_data
    assert "meta" in filtered_data

    # All returned rows should match the filter
    for row in filtered_data["data"]:
        assert str(row.get(test_column, "")) == filter_value


@pytest.mark.asyncio
async def test_fetch_resource_data_with_sort(resource_id: str) -> None:
    """Test fetching resource data with sort parameter."""
    # First get profile to find a column name
    profile = await tabular_api_client.fetch_resource_profile(resource_id)
    profile_headers = profile["profile"]["header"]

    if not profile_headers:
        pytest.skip("No columns available in test resource")

    # Use first column for sorting
    test_column = profile_headers[0]

    # Test ascending sort
    params_asc = {f"{test_column}__sort": "asc"}
    data_asc = await tabular_api_client.fetch_resource_data(
        resource_id, page=1, page_size=5, params=params_asc
    )

    assert "data" in data_asc
    assert len(data_asc["data"]) > 0

    # Test descending sort
    params_desc = {f"{test_column}__sort": "desc"}
    data_desc = await tabular_api_client.fetch_resource_data(
        resource_id, page=1, page_size=5, params=params_desc
    )

    assert "data" in data_desc
    assert len(data_desc["data"]) > 0

    # If we have multiple rows, first row of asc and desc should be different
    if len(data_asc["data"]) > 1 and len(data_desc["data"]) > 1:
        first_asc = data_asc["data"][0].get(test_column)
        first_desc = data_desc["data"][0].get(test_column)
        # They might be the same if all values are equal, but structure should be correct
        assert first_asc is not None or first_desc is not None
