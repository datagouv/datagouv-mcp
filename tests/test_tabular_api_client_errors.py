"""Unit tests for Tabular API error handling (mocked HTTP, no live API)."""

import re

import pytest
from pytest_httpx import HTTPXMock

from helpers import tabular_api_client

_MOCK_RID = "11111111-1111-1111-1111-111111111111"


@pytest.mark.asyncio
async def test_fetch_resource_data_404_llm_hint(httpx_mock: HTTPXMock) -> None:
    pattern = re.compile(rf".*/resources/{re.escape(_MOCK_RID)}/data/")
    httpx_mock.add_response(method="GET", url=pattern, status_code=404)
    with pytest.raises(tabular_api_client.ResourceNotAvailableError) as exc:
        await tabular_api_client.fetch_resource_data(_MOCK_RID, page_size=1)
    msg = str(exc.value)
    assert "search_datasets" in msg
    assert "list_dataset_resources" in msg


@pytest.mark.asyncio
async def test_fetch_resource_data_502_server_hint(httpx_mock: HTTPXMock) -> None:
    pattern = re.compile(rf".*/resources/{re.escape(_MOCK_RID)}/data/")
    httpx_mock.add_response(method="GET", url=pattern, status_code=502)
    with pytest.raises(tabular_api_client.TabularApiRequestError) as exc:
        await tabular_api_client.fetch_resource_data(_MOCK_RID, page_size=1)
    assert "try again" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_fetch_resource_data_400_with_column_detail(
    httpx_mock: HTTPXMock,
) -> None:
    pattern = re.compile(rf".*/resources/{re.escape(_MOCK_RID)}/data/")
    payload = {
        "errors": [
            {
                "code": "3e1d503c433b49e78b33165e2c715c5f",
                "title": "Database error",
                "detail": {
                    "code": "42703",
                    "message": "column x.nombre_piscines does not exist",
                },
            }
        ]
    }
    httpx_mock.add_response(method="GET", url=pattern, status_code=400, json=payload)
    with pytest.raises(tabular_api_client.TabularApiRequestError) as exc:
        await tabular_api_client.fetch_resource_data(_MOCK_RID, page_size=1)
    msg = str(exc.value)
    assert "rejected" in msg.lower()
    assert "does not exist" in msg.lower()
    assert "original error message" in msg.lower()
    assert "nombre_piscines" in msg.lower()


@pytest.mark.asyncio
async def test_fetch_resource_data_400_includes_api_uuid_message(
    httpx_mock: HTTPXMock,
) -> None:
    pattern = re.compile(rf".*/resources/{re.escape(_MOCK_RID)}/data/")
    payload = {
        "errors": [
            {
                "detail": {
                    "message": 'invalid input syntax for type uuid: "1234"',
                },
            }
        ]
    }
    httpx_mock.add_response(method="GET", url=pattern, status_code=400, json=payload)
    with pytest.raises(tabular_api_client.TabularApiRequestError) as exc:
        await tabular_api_client.fetch_resource_data(_MOCK_RID, page_size=1)
    msg = str(exc.value)
    assert "rejected" in msg.lower()
    assert "original error message" in msg.lower()
    assert "uuid" in msg.lower()


@pytest.mark.asyncio
async def test_fetch_resource_data_400_no_http_status_error(
    httpx_mock: HTTPXMock,
) -> None:
    pattern = re.compile(rf".*/resources/{re.escape(_MOCK_RID)}/data/")
    httpx_mock.add_response(method="GET", url=pattern, status_code=400, text="bad")
    with pytest.raises(tabular_api_client.TabularApiRequestError):
        await tabular_api_client.fetch_resource_data(_MOCK_RID, page_size=1)


@pytest.mark.asyncio
async def test_fetch_resource_profile_404_same_hint(httpx_mock: HTTPXMock) -> None:
    pattern = re.compile(rf".*/resources/{re.escape(_MOCK_RID)}/profile/")
    httpx_mock.add_response(method="GET", url=pattern, status_code=404)
    with pytest.raises(tabular_api_client.ResourceNotAvailableError) as exc:
        await tabular_api_client.fetch_resource_profile(_MOCK_RID)
    assert "search_datasets" in str(exc.value)
