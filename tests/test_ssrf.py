"""Tests for the SSRF-hardened HTTP client (producer URL fetches)."""

import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pytest

from helpers import datagouv_api_client
from helpers.ssrf import (
    BlockedAddressError,
    BlockedCategory,
    SSRFPolicy,
    SSRFProtectedAsyncSession,
    _proxy_url,
    blocked_reason,
    ssrf_async_session,
    ssrf_policy,
)

# niquests caches urllib proxy lookups; neutralize env so tests assert the
# code's behaviour rather than the machine's proxy settings.
pytestmark = pytest.mark.usefixtures("no_ambient_proxy")

DEFAULT_CASES = [
    ("127.0.0.1", BlockedCategory.LOOPBACK),
    ("127.0.1.1", BlockedCategory.LOOPBACK),
    ("::1", BlockedCategory.LOOPBACK),
    ("::ffff:7f00:1", BlockedCategory.LOOPBACK),
    ("::ffff:127.0.0.1", BlockedCategory.LOOPBACK),
    ("2002:7f00:1::", BlockedCategory.LOOPBACK),
    ("64:ff9b::7f00:1", BlockedCategory.LOOPBACK),
    ("64:ff9b::127.0.0.1", BlockedCategory.LOOPBACK),
    ("169.254.169.254", BlockedCategory.LINK_LOCAL),
    ("::ffff:a9fe:a9fe", BlockedCategory.LINK_LOCAL),
    ("2002:a9fe:a9fe::", BlockedCategory.LINK_LOCAL),
    ("64:ff9b::a9fe:a9fe", BlockedCategory.LINK_LOCAL),
    ("fe80::1", BlockedCategory.LINK_LOCAL),
    ("10.0.0.1", BlockedCategory.PRIVATE),
    ("192.168.1.1", BlockedCategory.PRIVATE),
    ("172.16.0.1", BlockedCategory.PRIVATE),
    ("::ffff:0a00:0001", BlockedCategory.PRIVATE),
    ("64:ff9b::a00:1", BlockedCategory.PRIVATE),
    ("fc00::1", BlockedCategory.PRIVATE),
    ("fec0::1", BlockedCategory.PRIVATE),
    ("feff:ffff:ffff:ffff:ffff:ffff:ffff:ffff", BlockedCategory.PRIVATE),
    ("100.64.0.1", BlockedCategory.PRIVATE),
    ("100.127.255.254", BlockedCategory.PRIVATE),
    ("::ffff:6440:1", BlockedCategory.PRIVATE),
    ("240.0.0.1", BlockedCategory.RESERVED),
    ("255.255.255.255", BlockedCategory.RESERVED),
    ("::7f00:1", BlockedCategory.RESERVED),
    ("::127.0.0.1", BlockedCategory.RESERVED),
    ("224.0.0.1", BlockedCategory.MULTICAST),
    ("ff00::1", BlockedCategory.MULTICAST),
    ("0.0.0.0", BlockedCategory.UNSPECIFIED),
    ("::", BlockedCategory.UNSPECIFIED),
    ("142.42.1.1", None),
    ("8.8.8.8", None),
    ("2a00:1450:4007:80e::2004", None),
    ("64:ff9b::8.8.8.8", None),
    ("64:ff9b::808:808", None),
]


def _clear_niquests_proxy_cache() -> None:
    from niquests.utils import getproxies, getproxies_environment

    for fn in (getproxies, getproxies_environment):
        cache_clear = getattr(fn, "cache_clear", None)
        if cache_clear is not None:
            cache_clear()


@pytest.fixture
def no_ambient_proxy(monkeypatch):
    for var in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "http_proxy",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
        "NO_PROXY",
        "no_proxy",
    ):
        monkeypatch.delenv(var, raising=False)
    _clear_niquests_proxy_cache()
    yield
    _clear_niquests_proxy_cache()


@pytest.mark.parametrize("address,expected", DEFAULT_CASES)
def test_blocked_reason_default_policy(address, expected):
    assert blocked_reason(address, SSRFPolicy()) is expected


def test_allow_loopback_permits_loopback_only():
    policy = SSRFPolicy(allow_loopback=True)
    assert blocked_reason("127.0.0.1", policy) is None
    assert blocked_reason("::ffff:7f00:1", policy) is None
    assert blocked_reason("2002:7f00:1::", policy) is None
    assert blocked_reason("64:ff9b::7f00:1", policy) is None
    assert blocked_reason("10.0.0.1", policy) is not None


def test_allow_private_does_not_permit_loopback():
    policy = SSRFPolicy(allow_private=True)
    assert blocked_reason("10.0.0.1", policy) is None
    assert blocked_reason("100.64.0.1", policy) is None
    assert blocked_reason("fec0::1", policy) is None
    assert blocked_reason("169.254.169.254", policy) is not None
    assert blocked_reason("127.0.0.1", policy) is not None
    assert blocked_reason("64:ff9b::7f00:1", policy) is not None
    assert blocked_reason("::7f00:1", policy) is not None


def test_allow_reserved_permits_reserved_only():
    policy = SSRFPolicy(allow_reserved=True)
    assert blocked_reason("240.0.0.1", policy) is None
    assert blocked_reason("::7f00:1", policy) is None
    assert blocked_reason("::127.0.0.1", policy) is None
    assert blocked_reason("127.0.0.1", policy) is not None
    assert blocked_reason("10.0.0.1", policy) is not None


def test_allow_private_does_not_permit_reserved():
    policy = SSRFPolicy(allow_private=True)
    assert blocked_reason("10.0.0.1", policy) is None
    assert blocked_reason("240.0.0.1", policy) is BlockedCategory.RESERVED


@pytest.mark.asyncio
async def test_session_blocks_loopback_before_connecting():
    session = SSRFProtectedAsyncSession()
    with pytest.raises(BlockedAddressError, match="loopback"):
        await session.get("http://127.0.0.1:9/", timeout=2)


@pytest.mark.asyncio
async def test_session_blocks_ipv4_mapped_loopback():
    session = SSRFProtectedAsyncSession()
    with pytest.raises(BlockedAddressError, match="loopback"):
        await session.get("http://[::ffff:7f00:1]:9/", timeout=2)


@pytest.mark.asyncio
async def test_session_blocks_an_https_target():
    session = SSRFProtectedAsyncSession()
    with pytest.raises(BlockedAddressError, match="loopback"):
        await session.get("https://127.0.0.1:9/", timeout=2)


@pytest.mark.asyncio
async def test_session_blocks_hostname_resolving_to_loopback():
    session = SSRFProtectedAsyncSession()
    with pytest.raises(BlockedAddressError, match="loopback"):
        await session.get("http://localhost:9/", timeout=2)


@pytest.mark.asyncio
async def test_session_rejects_disallowed_scheme():
    session = SSRFProtectedAsyncSession(
        SSRFPolicy(allowed_schemes=frozenset({"https"}))
    )
    with pytest.raises(BlockedAddressError, match="scheme"):
        await session.get("http://142.42.1.1/", timeout=2)


@pytest.mark.asyncio
async def test_session_refuses_an_environment_proxy(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://198.51.100.1:3128")
    monkeypatch.setenv("HTTPS_PROXY", "http://198.51.100.1:3128")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    _clear_niquests_proxy_cache()
    session = SSRFProtectedAsyncSession()
    with pytest.raises(BlockedAddressError, match="proxied"):
        await session.get("http://142.42.1.1/", timeout=2)


def test_proxy_url_ignores_no_proxy_bypass_list():
    assert (
        _proxy_url({"no": "127.0.0.1,localhost,circleci-internal-outer-build-agent"})
        is None
    )
    assert _proxy_url({"no_proxy": "localhost"}) is None
    assert (
        _proxy_url({"http": "http://198.51.100.1:3128"}) == "http://198.51.100.1:3128"
    )


@pytest.mark.asyncio
async def test_session_does_not_treat_environment_no_proxy_as_a_proxy(monkeypatch):
    """CircleCI sets NO_PROXY without HTTP_PROXY; that is a bypass list, not a proxy."""
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("http_proxy", raising=False)
    monkeypatch.delenv("https_proxy", raising=False)
    monkeypatch.setenv(
        "NO_PROXY", "127.0.0.1,localhost,circleci-internal-outer-build-agent"
    )
    _clear_niquests_proxy_cache()
    session = SSRFProtectedAsyncSession()
    with pytest.raises(BlockedAddressError, match="loopback"):
        await session.get("http://127.0.0.1:9/", timeout=2)


@pytest.mark.asyncio
async def test_session_refuses_explicit_proxy():
    session = SSRFProtectedAsyncSession()
    with pytest.raises(BlockedAddressError, match="proxied"):
        await session.get(
            "http://142.42.1.1/",
            timeout=2,
            proxies={"http": "http://198.51.100.1:3128"},
        )


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/redirect-to-metadata":
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
            self.end_headers()
            return
        body = b"hello from allowed host"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        pass


@pytest.fixture
def local_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address
    server.shutdown()


@pytest.mark.asyncio
async def test_session_allows_permitted_target_end_to_end(local_server):
    host, port = local_server
    session = SSRFProtectedAsyncSession(SSRFPolicy(allow_loopback=True))
    response = await session.get(f"http://{host}:{port}/", timeout=5)
    assert response.status_code == 200
    assert response.text == "hello from allowed host"


def resolving_to(addresses):
    """A ``socket.getaddrinfo`` stub answering with the given IPs, in order."""

    def getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port))
            for ip in addresses
        ]

    return getaddrinfo


@pytest.mark.asyncio
@pytest.mark.parametrize("blocked_first", [True, False])
async def test_session_connects_to_the_allowed_address_of_a_multi_homed_host(
    local_server, monkeypatch, blocked_first
):
    host, port = local_server
    addresses = ["10.0.0.1", host] if blocked_first else [host, "10.0.0.1"]
    monkeypatch.setattr(socket, "getaddrinfo", resolving_to(addresses))

    session = SSRFProtectedAsyncSession(SSRFPolicy(allow_loopback=True))
    response = await session.get(f"http://multi-homed.test:{port}/", timeout=5)

    assert response.status_code == 200
    assert response.text == "hello from allowed host"


@pytest.mark.asyncio
async def test_session_blocks_a_host_whose_addresses_are_all_forbidden(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo", resolving_to(["10.0.0.1", "192.168.1.1"])
    )

    session = SSRFProtectedAsyncSession()
    with pytest.raises(BlockedAddressError, match="private"):
        await session.get("http://internal-only.test:9/", timeout=2)


@pytest.mark.asyncio
async def test_session_blocks_a_redirect_to_a_forbidden_target(local_server):
    host, port = local_server
    session = SSRFProtectedAsyncSession(SSRFPolicy(allow_loopback=True))
    with pytest.raises(BlockedAddressError, match="link-local"):
        await session.get(f"http://{host}:{port}/redirect-to-metadata", timeout=5)


@pytest.mark.asyncio
async def test_fetch_openapi_spec_blocks_loopback():
    with pytest.raises(BlockedAddressError, match="loopback"):
        await datagouv_api_client.fetch_openapi_spec("http://127.0.0.1:9/")


@pytest.mark.asyncio
async def test_fetch_openapi_spec_blocks_cloud_metadata():
    with pytest.raises(BlockedAddressError, match="link-local"):
        await datagouv_api_client.fetch_openapi_spec(
            "http://169.254.169.254/latest/meta-data/"
        )


@pytest.mark.asyncio
async def test_fetch_openapi_spec_blocks_rfc1918():
    with pytest.raises(BlockedAddressError, match="private"):
        await datagouv_api_client.fetch_openapi_spec("http://192.168.1.1/")


@pytest.mark.asyncio
async def test_fetch_openapi_spec_blocks_file_scheme():
    with pytest.raises(BlockedAddressError, match="scheme"):
        await datagouv_api_client.fetch_openapi_spec("file:///etc/passwd")


def test_ssrf_policy_defaults_block_private_and_local(monkeypatch):
    monkeypatch.delenv("URLS_ALLOW_LOCAL", raising=False)
    monkeypatch.delenv("URLS_ALLOW_PRIVATE", raising=False)
    policy = ssrf_policy()
    assert blocked_reason("127.0.0.1", policy) is BlockedCategory.LOOPBACK
    assert blocked_reason("10.0.0.1", policy) is BlockedCategory.PRIVATE
    assert blocked_reason("169.254.169.254", policy) is BlockedCategory.LINK_LOCAL


def test_ssrf_policy_urls_allow_private_includes_link_local(monkeypatch):
    monkeypatch.delenv("URLS_ALLOW_LOCAL", raising=False)
    monkeypatch.setenv("URLS_ALLOW_PRIVATE", "1")
    policy = ssrf_policy()
    assert blocked_reason("10.0.0.1", policy) is None
    assert blocked_reason("169.254.169.254", policy) is None
    assert blocked_reason("127.0.0.1", policy) is BlockedCategory.LOOPBACK


def test_ssrf_async_session_uses_env_policy(monkeypatch):
    monkeypatch.delenv("URLS_ALLOW_LOCAL", raising=False)
    monkeypatch.delenv("URLS_ALLOW_PRIVATE", raising=False)
    session = ssrf_async_session()
    assert isinstance(session, SSRFProtectedAsyncSession)
    assert session.policy.allow_loopback is False
