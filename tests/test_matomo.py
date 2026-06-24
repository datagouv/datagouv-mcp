"""Tests for Matomo tracking helpers."""

from urllib.parse import parse_qs

import pytest
from niquests_mock import MockRouter
from niquests_mock.router import MockRoute

import helpers.matomo as matomo

_MATOMO_POST_URL = "https://matomo.example/matomo.php"


@pytest.fixture
def matomo_post_route(niquests_mock: MockRouter) -> MockRoute:
    return niquests_mock.post(_MATOMO_POST_URL).respond(status_code=200)


@pytest.mark.asyncio
async def test_track_matomo_tool_sends_event_fields(matomo_post_route, monkeypatch):
    monkeypatch.setattr(matomo, "MATOMO_URL", "https://matomo.example")
    monkeypatch.setattr(matomo, "MATOMO_SITE_ID", "7")
    monkeypatch.setattr(matomo, "MATOMO_AUTH_TOKEN", None)  # omitted from POST body
    url_tok, ua_tok, cip_tok = matomo.apply_matomo_request_context(
        {"user-agent": "ToolUA/2", "host": "mcp.example"},
        "/mcp",
    )
    try:
        await matomo.track_matomo_tool("search_datasets")
    finally:
        matomo.reset_matomo_request_context(url_tok, ua_tok, cip_tok)

    assert matomo_post_route.called
    body = matomo_post_route.calls[0].request.body
    params = parse_qs(body, strict_parsing=True)
    assert params["idsite"] == ["7"]
    assert params["e_c"] == ["MCP"]
    assert params["e_a"] == ["search_datasets"]
    assert params["ca"] == ["1"]
    assert params["url"] == ["https://mcp.example/mcp"]
    assert params["ua"] == ["ToolUA/2"]
    assert "token_auth" not in params


@pytest.mark.asyncio
async def test_track_matomo_tool_forwards_cip_from_context(
    matomo_post_route, monkeypatch
):
    monkeypatch.setattr(matomo, "MATOMO_URL", "https://matomo.example")
    monkeypatch.setattr(matomo, "MATOMO_SITE_ID", "7")
    monkeypatch.setattr(matomo, "MATOMO_AUTH_TOKEN", "tok")
    url_tok, ua_tok, cip_tok = matomo.apply_matomo_request_context(
        {
            "user-agent": "ToolUA/2",
            "host": "mcp.example",
            "x-forwarded-for": "203.0.113.42",
        },
        "/mcp",
    )
    try:
        await matomo.track_matomo_tool("search_datasets")
    finally:
        matomo.reset_matomo_request_context(url_tok, ua_tok, cip_tok)

    body = matomo_post_route.calls[0].request.body
    params = parse_qs(body, strict_parsing=True)
    assert params["cip"] == ["203.0.113.42"]
    assert params["token_auth"] == ["tok"]


@pytest.mark.asyncio
async def test_post_matomo_skips_when_not_configured(matomo_post_route, monkeypatch):
    monkeypatch.setattr(matomo, "MATOMO_URL", "")
    monkeypatch.setattr(matomo, "MATOMO_SITE_ID", "1")
    await matomo.track_matomo_tool("search_datasets")
    assert not matomo_post_route.called


def test_matomo_tool_event_for_uses_override():
    token = matomo.apply_matomo_tool_event_action("health_check")
    try:
        assert matomo.matomo_tool_event_for("search_datasets") == "health_check"
    finally:
        matomo.reset_matomo_tool_event_action(token)
