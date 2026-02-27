import httpx
import pytest

from helpers import metrics_api_client


@pytest.mark.asyncio
async def test_get_metrics_uses_generated_id_field_and_limit_cap() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/datasets/data/")
        assert request.url.params["dataset_id__exact"] == "dataset-123"
        assert request.url.params["metric_month__sort"] == "desc"
        assert request.url.params["page_size"] == "100"
        return httpx.Response(200, json={"data": [{"dataset_id": "dataset-123"}]})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://metrics-api.test/"
    ) as session:
        metrics = await metrics_api_client.get_metrics(
            "datasets",
            " dataset-123 ",
            limit=500,
            session=session,
        )

    assert metrics == [{"dataset_id": "dataset-123"}]


@pytest.mark.asyncio
async def test_get_metrics_csv_calls_csv_endpoint() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/resources/data/csv/")
        assert request.url.params["resource_id__exact"] == "res-1"
        return httpx.Response(200, text="metric_month,resource_id\n2026-01,res-1\n")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://metrics-api.test/"
    ) as session:
        csv_data = await metrics_api_client.get_metrics_csv(
            "resources",
            "res-1",
            session=session,
        )

    assert "resource_id" in csv_data


@pytest.mark.asyncio
async def test_get_metrics_rejects_blank_id_value() -> None:
    with pytest.raises(ValueError, match="id_value cannot be empty"):
        await metrics_api_client.get_metrics("datasets", "   ")
