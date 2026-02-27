import httpx
import pytest

from helpers import datagouv_api_client


def test_extract_tags_normalizes_strings_and_dicts() -> None:
    raw = ["  transport  ", {"name": "mobility"}, {"name": ""}, 123, None]
    assert datagouv_api_client._extract_tags(raw) == ["transport", "mobility"]


@pytest.mark.asyncio
async def test_fetch_openapi_spec_accepts_json_mapping() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text='{"openapi":"3.1.0","paths":{}}')

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://spec.test/"
    ) as session:
        spec = await datagouv_api_client.fetch_openapi_spec(
            "https://spec.test/openapi.json",
            session=session,
        )

    assert spec["openapi"] == "3.1.0"


@pytest.mark.asyncio
async def test_fetch_openapi_spec_accepts_yaml_mapping() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="openapi: 3.0.0\npaths: {}\n")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://spec.test/"
    ) as session:
        spec = await datagouv_api_client.fetch_openapi_spec(
            "https://spec.test/openapi.yaml",
            session=session,
        )

    assert spec["openapi"] == "3.0.0"


@pytest.mark.asyncio
async def test_fetch_openapi_spec_rejects_non_mapping_payload() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text='["not-a-mapping"]')

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://spec.test/"
    ) as session:
        with pytest.raises(ValueError, match="Could not parse OpenAPI spec"):
            await datagouv_api_client.fetch_openapi_spec(
                "https://spec.test/openapi.json",
                session=session,
            )


@pytest.mark.asyncio
async def test_get_resources_for_dataset_returns_metadata_without_n_plus_one() -> None:
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            200,
            json={
                "id": "dataset-1",
                "title": "Dataset title",
                "resources": [
                    {
                        "id": "res-1",
                        "title": "Resource title",
                        "format": "csv",
                        "filesize": 1024,
                        "mime": "text/csv",
                        "type": "main",
                        "url": "https://example.com/res.csv",
                    }
                ],
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.test/"
    ) as session:
        result = await datagouv_api_client.get_resources_for_dataset(
            "dataset-1", session=session
        )

    assert call_count == 1
    assert result["dataset"]["id"] == "dataset-1"
    assert result["resources"] == [
        {
            "id": "res-1",
            "title": "Resource title",
            "format": "csv",
            "filesize": 1024,
            "mime": "text/csv",
            "type": "main",
            "url": "https://example.com/res.csv",
        }
    ]
