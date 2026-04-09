"""Tests for Matomo tracking helpers."""

from urllib.parse import parse_qs

import pytest

import helpers.matomo as matomo


@pytest.mark.asyncio
async def test_track_matomo_request_sends_expected_form_fields(
    httpx_mock,
    monkeypatch,
):
    monkeypatch.setattr(matomo, "MATOMO_URL", "https://matomo.example")
    monkeypatch.setattr(matomo, "MATOMO_SITE_ID", "7")
    monkeypatch.setattr(matomo, "MATOMO_AUTH_TOKEN", "tok")
    httpx_mock.add_response()

    await matomo.track_matomo_request(
        "https://mcp.example/mcp",
        "/mcp",
        {"user-agent": "MCPTest/1"},
    )

    requests = httpx_mock.get_requests()
    assert len(requests) == 1
    assert str(requests[0].url) == "https://matomo.example/matomo.php"
    body = requests[0].content.decode()
    params = parse_qs(body, strict_parsing=True)
    assert params["idsite"] == ["7"]
    assert params["rec"] == ["1"]
    assert params["url"] == ["https://mcp.example/mcp"]
    assert params["action_name"] == ["MCP Request: /mcp"]
    assert params["ua"] == ["MCPTest/1"]
    assert params["token_auth"] == ["tok"]
    assert "e_c" not in params
    assert "ca" not in params


@pytest.mark.asyncio
async def test_track_matomo_tool_sends_event_fields(httpx_mock, monkeypatch):
    monkeypatch.setattr(matomo, "MATOMO_URL", "https://matomo.example")
    monkeypatch.setattr(matomo, "MATOMO_SITE_ID", "7")
    monkeypatch.setattr(matomo, "MATOMO_AUTH_TOKEN", None)  # omitted from POST body
    url_tok, ua_tok = matomo.apply_matomo_request_context(
        {"user-agent": "ToolUA/2", "host": "mcp.example"},
        "/mcp",
    )
    httpx_mock.add_response()
    try:
        await matomo.track_matomo_tool("search_datasets")
    finally:
        matomo.reset_matomo_request_context(url_tok, ua_tok)

    requests = httpx_mock.get_requests()
    assert len(requests) == 1
    body = requests[0].content.decode()
    params = parse_qs(body, strict_parsing=True)
    assert params["idsite"] == ["7"]
    assert params["e_c"] == ["MCP"]
    assert params["e_a"] == ["search_datasets"]
    assert params["ca"] == ["1"]
    assert params["url"] == ["https://mcp.example/mcp"]
    assert params["ua"] == ["ToolUA/2"]
    assert "token_auth" not in params


@pytest.mark.asyncio
async def test_post_matomo_skips_when_not_configured(httpx_mock, monkeypatch):
    monkeypatch.setattr(matomo, "MATOMO_URL", "")
    monkeypatch.setattr(matomo, "MATOMO_SITE_ID", "1")
    await matomo.track_matomo_request(
        "https://x/y",
        "/y",
        {},
    )
    assert len(httpx_mock.get_requests()) == 0
