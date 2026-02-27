import os

import pytest

from helpers import metrics_api_client

pytestmark = pytest.mark.integration


@pytest.fixture
def known_dataset_id() -> str:
    # Same dataset id used in other integration tests (Transports dataset).
    return os.getenv("TEST_DATASET_ID", "55e4129788ee386899a46ec1")


@pytest.fixture
def known_resource_id() -> str:
    # Resource id from the "Élus locaux" dataset (known to have downloads).
    return os.getenv(
        "TEST_RESOURCE_ID",
        "3b6b2281-b9d9-4959-ae9d-c2c166dff118",
    )


@pytest.mark.asyncio
async def test_get_metrics_datasets(known_dataset_id):
    metrics = await metrics_api_client.get_metrics(
        "datasets",
        known_dataset_id,
        limit=3,
    )

    assert len(metrics) > 0
    assert all(entry["dataset_id"] == known_dataset_id for entry in metrics)

    months = [entry["metric_month"] for entry in metrics]
    assert months == sorted(months, reverse=True)


@pytest.mark.asyncio
async def test_get_metrics_resources(known_resource_id):
    metrics = await metrics_api_client.get_metrics(
        "resources",
        known_resource_id,
        limit=2,
    )

    assert len(metrics) > 0
    assert all(entry["resource_id"] == known_resource_id for entry in metrics)


@pytest.mark.asyncio
async def test_get_metrics_custom_id_field():
    """Test that custom id_field parameter works."""
    # Using a known dataset ID with explicit field name
    known_dataset_id = os.getenv("TEST_DATASET_ID", "55e4129788ee386899a46ec1")
    metrics = await metrics_api_client.get_metrics(
        "datasets",
        known_dataset_id,
        id_field="dataset_id",
        limit=1,
    )

    assert len(metrics) > 0
    assert all(entry["dataset_id"] == known_dataset_id for entry in metrics)


@pytest.mark.asyncio
async def test_get_metrics_time_granularity(known_dataset_id):
    """Test that time_granularity parameter works (currently only 'month' is supported)."""
    metrics = await metrics_api_client.get_metrics(
        "datasets",
        known_dataset_id,
        time_granularity="month",
        limit=2,
    )

    assert len(metrics) > 0
    assert all("metric_month" in entry for entry in metrics)


@pytest.mark.asyncio
async def test_get_metrics_sort_order(known_dataset_id):
    """Test that sort_order parameter works."""
    metrics_desc = await metrics_api_client.get_metrics(
        "datasets",
        known_dataset_id,
        sort_order="desc",
        limit=3,
    )
    metrics_asc = await metrics_api_client.get_metrics(
        "datasets",
        known_dataset_id,
        sort_order="asc",
        limit=3,
    )

    assert len(metrics_desc) > 0
    assert len(metrics_asc) > 0

    months_desc = [entry["metric_month"] for entry in metrics_desc]
    months_asc = [entry["metric_month"] for entry in metrics_asc]

    assert months_desc == sorted(months_desc, reverse=True)
    assert months_asc == sorted(months_asc)


@pytest.mark.asyncio
async def test_get_metrics_invalid_model():
    """Test that invalid model raises an error."""
    with pytest.raises(Exception):
        # Use a valid ID format but invalid model
        await metrics_api_client.get_metrics(
            "unknown_model",
            "55e4129788ee386899a46ec1",
        )


@pytest.mark.asyncio
async def test_get_metrics_csv_datasets(known_dataset_id):
    """Test fetching metrics as CSV for datasets."""
    csv_content = await metrics_api_client.get_metrics_csv(
        "datasets",
        known_dataset_id,
    )

    assert csv_content is not None
    assert len(csv_content) > 0
    # Check it's CSV format (has header and data rows)
    lines = csv_content.strip().split("\n")
    assert len(lines) > 1  # Header + at least one data row
    assert "dataset_id" in lines[0]  # Header contains dataset_id
    assert "metric_month" in lines[0]  # Header contains metric_month
    # Check that the dataset_id appears in the data
    assert any(known_dataset_id in line for line in lines[1:])


@pytest.mark.asyncio
async def test_get_metrics_csv_resources(known_resource_id):
    """Test fetching metrics as CSV for resources."""
    csv_content = await metrics_api_client.get_metrics_csv(
        "resources",
        known_resource_id,
    )

    assert csv_content is not None
    assert len(csv_content) > 0
    lines = csv_content.strip().split("\n")
    assert len(lines) > 1
    assert "resource_id" in lines[0]
    assert any(known_resource_id in line for line in lines[1:])


@pytest.mark.asyncio
async def test_get_metrics_csv_with_custom_params():
    """Test that get_metrics_csv works with various parameters."""
    known_dataset_id = os.getenv("TEST_DATASET_ID", "55e4129788ee386899a46ec1")
    csv_content = await metrics_api_client.get_metrics_csv(
        "datasets",
        known_dataset_id,
        sort_order="desc",
    )

    assert csv_content is not None
    assert len(csv_content) > 0
    lines = csv_content.strip().split("\n")
    assert len(lines) > 1  # Header + data rows
