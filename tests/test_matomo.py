"""Tests for Matomo tracking helpers."""

import asyncio
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


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (
            (
                b'{"jsonrpc":"2.0","id":1,"method":"initialize",'
                b'"params":{"clientInfo":{"name":"claude-ai","version":"1.0"}}}'
            ),
            True,
        ),
        (b'{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{}}', False),
        (b'{"jsonrpc":"2.0","method":"notifications/initialized"}', False),
        (b'"initialize" not json {', False),
        (b"", False),
    ],
)
def test_is_initialize_request(body, expected):
    assert matomo.is_initialize_request(body) is expected


_INITIALIZE_BODY = (
    b'{"jsonrpc":"2.0","id":1,"method":"initialize",'
    b'"params":{"protocolVersion":"2025-06-18","capabilities":{},'
    b'"clientInfo":{"name":"Cursor","version":"2.0"}}}'
)


async def _drain_background_tasks() -> None:
    current = asyncio.current_task()
    pending = [t for t in asyncio.all_tasks() if t is not current]
    if pending:
        await asyncio.gather(*pending)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "status", "expected_events"),
    [
        (_INITIALIZE_BODY, 200, 1),
        (_INITIALIZE_BODY, 406, 0),
        (b'{"jsonrpc":"2.0","id":2,"method":"tools/list"}', 200, 0),
    ],
)
async def test_track_initialize_requests(
    matomo_post_route, monkeypatch, body, status, expected_events
):
    monkeypatch.setattr(matomo, "MATOMO_URL", "https://matomo.example")
    monkeypatch.setattr(matomo, "MATOMO_SITE_ID", "7")
    request = {"type": "http.request", "body": body, "more_body": False}
    response_start = {"type": "http.response.start", "status": status}
    sent: list[dict] = []

    async def receive() -> dict:
        return request

    async def send(message: dict) -> None:
        sent.append(message)

    url_tok, ua_tok, cip_tok = matomo.apply_matomo_request_context(
        {"user-agent": "Cursor/2.0", "host": "mcp.example"},
        "/mcp",
    )
    wrapped_receive, wrapped_send = matomo.track_initialize_requests(receive, send)
    try:
        received = await wrapped_receive()
        await wrapped_send(response_start)
    finally:
        matomo.reset_matomo_request_context(url_tok, ua_tok, cip_tok)
    await _drain_background_tasks()

    # Messages are passed through unchanged
    assert received == request
    assert sent == [response_start]
    assert len(matomo_post_route.calls) == expected_events
    if expected_events:
        params = parse_qs(matomo_post_route.calls[0].request.body, strict_parsing=True)
        assert params["e_c"] == ["sessions"]
        assert params["e_a"] == ["initialize"]
        # e_n stays based on the User-Agent, consistent with tool events
        assert params["e_n"] == ["Cursor"]


@pytest.fixture(scope="module")
def asgi_client():
    from starlette.testclient import TestClient

    import main

    # The MCP session manager can only be started once per process
    with TestClient(main.asgi_app, base_url="http://localhost:8000") as client:
        yield client


@pytest.mark.parametrize(
    ("headers", "expected_status", "expected_events"),
    [
        ({}, 200, 1),
        ({"host": "evil.example"}, 421, 0),
        ({"accept": "text/html"}, 406, 0),
        ({"content-type": "text/plain"}, 400, 0),
    ],
)
def test_initialize_tracking_through_asgi_app(
    asgi_client, monkeypatch, headers, expected_status, expected_events
):
    """Only initialize requests accepted by the MCP server are counted."""
    events: list[tuple[str, str | None]] = []

    async def fake_track_matomo_event(name, action=None, category=None):
        events.append((name, category))

    monkeypatch.setattr(matomo, "track_matomo_event", fake_track_matomo_event)
    request_headers = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
        **headers,
    }
    response = asgi_client.post(
        "/mcp", content=_INITIALIZE_BODY, headers=request_headers
    )

    assert response.status_code == expected_status
    assert events == [("initialize", "sessions")] * expected_events
