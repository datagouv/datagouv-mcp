import pytest
from httpx import ASGITransport, AsyncClient

from main import asgi_app


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok_status():
    transport = ASGITransport(app=asgi_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("status") == "ok"
    assert "timestamp" in payload
