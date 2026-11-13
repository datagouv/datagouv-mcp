"""Tests for Matomo tracking helpers."""

from urllib.parse import parse_qs

import pytest
from niquests_mock import MockRouter
from niquests_mock.router import MockRoute

from helpers import matomo

_MATOMO_POST_URL = "https://matomo.example/matomo.php"


@pytest.fixture
def matomo_post_route(niquests_mock: MockRouter) -> MockRoute:
    return niquests_mock.post(_MATOMO_POST_URL).respond(status_code=200)


@pytest.mark.asyncio
async def test_track_matomo_event_sends_event_fields(matomo_post_route, monkeypatch):
    monkeypatch.setattr(matomo, "MATOMO_URL", "https://matomo.example")
    monkeypatch.setattr(matomo, "MATOMO_SITE_ID", "7")
    monkeypatch.setattr(matomo, "MATOMO_AUTH_TOKEN", None)  # omitted from POST body
    url_tok, ua_tok, cip_tok = matomo.apply_matomo_request_context(
        {"user-agent": "ToolUA/2", "host": "mcp.example"},
        "/mcp",
    )
    try:
        await matomo.track_matomo_event("search_datasets")
    finally:
        matomo.reset_matomo_request_context(url_tok, ua_tok, cip_tok)

    assert matomo_post_route.called
    body = matomo_post_route.calls[0].request.body
    params = parse_qs(body, strict_parsing=True)
    assert params["idsite"] == ["7"]
    assert params["e_c"] == ["tools"]
    assert params["e_a"] == ["search_datasets"]
    assert params["ca"] == ["1"]
    assert params["url"] == ["https://mcp.example/mcp"]
    assert params["ua"] == ["ToolUA/2"]
    assert params["e_n"] == ["ToolUA"]
    assert "token_auth" not in params


@pytest.mark.asyncio
async def test_track_matomo_event_forwards_cip_from_context(
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
        await matomo.track_matomo_event("search_datasets")
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
    await matomo.track_matomo_event("search_datasets")
    assert not matomo_post_route.called


@pytest.mark.asyncio
async def test_track_matomo_event_action_and_category_override(
    matomo_post_route, monkeypatch
):
    monkeypatch.setattr(matomo, "MATOMO_URL", "https://matomo.example")
    monkeypatch.setattr(matomo, "MATOMO_SITE_ID", "7")

    await matomo.track_matomo_event(
        "search_datasets",
        action="health_check",
        category="health_check",
    )
    explicit_body = matomo_post_route.calls[0].request.body
    explicit_params = parse_qs(explicit_body, strict_parsing=True)
    assert explicit_params["e_c"] == ["health_check"]
    assert explicit_params["e_a"] == ["health_check"]

    override_token = matomo.apply_matomo_event_override(
        action="health_check",
        category="health_check",
    )
    try:
        await matomo.track_matomo_event("search_datasets")
    finally:
        matomo.reset_matomo_event_override(override_token)

    context_body = matomo_post_route.calls[1].request.body
    context_params = parse_qs(context_body, strict_parsing=True)
    assert context_params["e_c"] == ["health_check"]
    assert context_params["e_a"] == ["health_check"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("user_agent", "expected"),
    [
        ("AssistantIA/1.2.0 (+https://example.org)", "AssistantIA"),
        ("NoVersionClient", "NoVersionClient"),
        ("x" * 80, "x" * 50),
    ],
)
async def test_track_matomo_event_sends_client_name(
    matomo_post_route, monkeypatch, user_agent, expected
):
    monkeypatch.setattr(matomo, "MATOMO_URL", "https://matomo.example")
    monkeypatch.setattr(matomo, "MATOMO_SITE_ID", "7")
    url_tok, ua_tok, cip_tok = matomo.apply_matomo_request_context(
        {"user-agent": user_agent, "host": "mcp.example"},
        "/mcp",
    )
    try:
        await matomo.track_matomo_event("search_datasets")
    finally:
        matomo.reset_matomo_request_context(url_tok, ua_tok, cip_tok)

    body = matomo_post_route.calls[0].request.body
    assert parse_qs(body, strict_parsing=True)["e_n"] == [expected]


@pytest.mark.asyncio
async def test_track_matomo_event_omits_client_name_without_user_agent(
    matomo_post_route, monkeypatch
):
    monkeypatch.setattr(matomo, "MATOMO_URL", "https://matomo.example")
    monkeypatch.setattr(matomo, "MATOMO_SITE_ID", "7")
    url_tok, ua_tok, cip_tok = matomo.apply_matomo_request_context(
        {"host": "mcp.example"},
        "/mcp",
    )
    try:
        await matomo.track_matomo_event("search_datasets")
    finally:
        matomo.reset_matomo_request_context(url_tok, ua_tok, cip_tok)

    body = matomo_post_route.calls[0].request.body
    assert "e_n" not in parse_qs(body, strict_parsing=True)
