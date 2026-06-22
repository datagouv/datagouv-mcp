import niquests
import pytest

from main import asgi_app


@pytest.mark.asyncio
async def test_health_endpoint_returns_valid_response():
    async with niquests.AsyncSession(app=asgi_app) as client:
        response = await client.get("/health")

    assert response.status_code in (200, 503)
    payload = response.json()
    assert "status" in payload
    if response.status_code == 200:
        assert payload["status"] == "ok"
        assert "uptime_since" in payload
        assert "version" in payload
        assert isinstance(payload.get("version"), str)
        assert "env" in payload
        assert "data_env" in payload
    else:
        assert payload["status"] == "mcp_unavailable"
