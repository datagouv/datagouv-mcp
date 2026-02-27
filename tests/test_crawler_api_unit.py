import httpx
import pytest

from helpers import crawler_api_client


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    crawler_api_client.clear_cache()


@pytest.mark.asyncio
async def test_fetch_resource_exceptions_uses_cache() -> None:
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=[{"resource_id": "res-1"}])

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://crawler-api.test/"
    ) as session:
        first = await crawler_api_client.fetch_resource_exceptions(session=session)
        second = await crawler_api_client.fetch_resource_exceptions(session=session)

    assert first == {"res-1"}
    assert second == {"res-1"}
    assert call_count == 1


@pytest.mark.asyncio
async def test_fetch_resource_exceptions_force_refresh_bypasses_cache() -> None:
    responses = [
        [{"resource_id": "res-1"}],
        [{"resource_id": "res-2"}],
    ]

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=responses.pop(0))

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://crawler-api.test/"
    ) as session:
        first = await crawler_api_client.fetch_resource_exceptions(session=session)
        refreshed = await crawler_api_client.fetch_resource_exceptions(
            session=session,
            force_refresh=True,
        )

    assert first == {"res-1"}
    assert refreshed == {"res-2"}


@pytest.mark.asyncio
async def test_fetch_resource_exceptions_returns_stale_cache_on_error() -> None:
    async def ok_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"resource_id": "res-1"}])

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(ok_handler), base_url="https://crawler-api.test/"
    ) as session:
        cached = await crawler_api_client.fetch_resource_exceptions(session=session)

    async def failing_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down", request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(failing_handler),
        base_url="https://crawler-api.test/",
    ) as session:
        stale = await crawler_api_client.fetch_resource_exceptions(
            session=session,
            force_refresh=True,
        )

    assert cached == {"res-1"}
    assert stale == {"res-1"}
