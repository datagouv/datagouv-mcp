import httpx
import pytest

from helpers import tabular_api_client


@pytest.mark.asyncio
async def test_fetch_resource_data_clamps_pagination_values() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["page"] == "1"
        assert request.url.params["page_size"] == "1"
        return httpx.Response(
            200,
            json={
                "data": [],
                "meta": {"page": 1, "page_size": 1, "total": 0},
                "links": {},
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://tabular-api.test/"
    ) as session:
        result = await tabular_api_client.fetch_resource_data(
            "resource-id",
            page=0,
            page_size=0,
            session=session,
        )

    assert result["meta"]["page"] == 1
    assert result["meta"]["page_size"] == 1


@pytest.mark.asyncio
async def test_fetch_resource_data_raises_not_available_on_404() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "not found"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://tabular-api.test/"
    ) as session:
        with pytest.raises(tabular_api_client.ResourceNotAvailableError):
            await tabular_api_client.fetch_resource_data("resource-id", session=session)


@pytest.mark.asyncio
async def test_fetch_resource_profile_cleans_quoted_headers() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "profile": {
                    "header": ['"city"', "population", '"postal_code"'],
                    "columns": {},
                }
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://tabular-api.test/"
    ) as session:
        result = await tabular_api_client.fetch_resource_profile(
            "resource-id", session=session
        )

    assert result["profile"]["header"] == ["city", "population", "postal_code"]
