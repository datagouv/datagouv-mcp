"""
SSRF-hardened HTTP client for niquests (urllib3-future).

This module is intentionally self-contained: it has no dependency on MCP
config. It only depends on the standard library, niquests and urllib3.

Why this exists
---------------
The naive way to prevent Server-Side Request Forgery is to validate the URL
string (or resolve its hostname) *before* handing it to the HTTP client. That
approach is structurally broken:

* **DNS rebinding (TOCTOU)** — the hostname resolved at validation time is not
  the address the socket connects to later. An attacker returns a public IP for
  the check and a private one for the real request.
* **Address representation gaps** — IPv4-mapped IPv6 (``::ffff:7f00:1``),
  6to4, NAT64… a string filter keeps missing new encodings.
* **Redirects** — a validated URL can ``302`` to an internal target.
* **Proxies** — ``HTTP_PROXY`` would connect to the proxy, not the destination,
  and the proxy would then fetch the internal URL.

The only robust fix is to validate the IP **at the moment the socket connects**,
using the very address the socket will use. urllib3-future's resolver
``create_connection`` calls ``getaddrinfo`` then ``connect()`` on those records
with no second lookup — wrapping ``getaddrinfo`` is therefore connect-time
validation of the same resolution. Redirect hops open a new guarded connection.
Proxies are refused outright.

IP classification matches udata's ``udata.ssrf`` (opendatateam/udata#3877) so
the MCP uses the same policy as ``URLS_ALLOW_*`` / ``uris.validate``.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit

import niquests
from niquests.models import PreparedRequest, Request
from niquests.utils import create_async_resolver, create_resolver, resolve_proxies
from urllib3.contrib.resolver import BaseResolver, ProtocolResolver
from urllib3.contrib.resolver._async import AsyncBaseResolver

__all__ = [
    "SSRFPolicy",
    "BlockedAddressError",
    "BlockedCategory",
    "blocked_reason",
    "SSRFProtectedSession",
    "SSRFProtectedAsyncSession",
    "ssrf_policy_for",
]

_AddrInfo = tuple[
    socket.AddressFamily,
    socket.SocketKind,
    int,
    str | bytes,
    tuple[str, int] | tuple[str, int, int, int],
]


class BlockedCategory(StrEnum):
    """Why an address is refused."""

    MULTICAST = "multicast address"
    UNSPECIFIED = "unspecified address"
    LOOPBACK = "loopback address"
    LINK_LOCAL = "link-local address"
    PRIVATE = "private address"
    RESERVED = "reserved address"


class BlockedAddressError(Exception):
    """
    Raised when a request targets an address forbidden by the policy.

    It deliberately does **not** subclass ``OSError`` / niquests exceptions:
    urllib3's connection retry logic catches ``OSError`` and would otherwise
    swallow the block or retry it. Being a plain ``Exception`` lets it
    propagate straight out of ``session.request()``.
    """


_IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

# RFC 6052 well-known prefix: a DNS64 resolver answers every IPv4-only name with
# ``64:ff9b::/96``, and the NAT64 gateway routes it to that IPv4. The stdlib
# has no accessor for it (only the RFC 8215 local-use ``64:ff9b:1::/48`` is
# listed as private), so the prefix is spelled out here.
_NAT64_WELL_KNOWN_PREFIX = ipaddress.IPv6Network("64:ff9b::/96")


@dataclass(frozen=True)
class SSRFPolicy:
    """
    Which destinations an SSRF-protected session is allowed to reach.

    Everything that is not a globally routable (public) address is blocked by
    default. Individual categories can be re-enabled — typically only in tests
    or trusted internal tooling. Matches udata ``URLS_ALLOW_*`` when mapped
    through :func:`ssrf_policy_for`.
    """

    allow_loopback: bool = False  # 127.0.0.0/8, ::1
    allow_private: bool = False  # RFC1918, ULA (fc00::/7), CGNAT…
    allow_link_local: bool = False  # 169.254.0.0/16, fe80::/10 (cloud metadata!)
    allow_reserved: bool = False  # IETF-reserved / IPv4-compatible IPv6, etc.
    allowed_schemes: frozenset[str] = frozenset({"http", "https"})


def ssrf_policy_for(
    *,
    local: bool = False,
    private: bool = False,
    schemes: Sequence[str] = ("http", "https"),
) -> SSRFPolicy:
    """
    Map udata ``URLS_ALLOW_*`` semantics onto an :class:`SSRFPolicy`.

    ``URLS_ALLOW_LOCAL`` drives loopback; ``URLS_ALLOW_PRIVATE`` drives
    private, link-local and reserved (same grouping as udata.http).
    """
    return SSRFPolicy(
        allow_loopback=local,
        allow_private=private,
        allow_link_local=private,
        allow_reserved=private,
        allowed_schemes=frozenset(schemes),
    )


def _unwrap_embedded_ipv4(ip: _IPAddress) -> _IPAddress:
    """
    Return the embedded IPv4 address for IPv6 forms that route to one.

    ``::ffff:7f00:1``, ``2002:7f00:1::`` and ``64:ff9b::7f00:1`` all reach
    ``127.0.0.1`` but their IPv6 object reports ``is_loopback == False``.
    """
    if ip.version == 6:
        mapped = ip.ipv4_mapped
        if mapped is not None:
            return mapped
        sixtofour = ip.sixtofour
        if sixtofour is not None:
            return sixtofour
        if ip in _NAT64_WELL_KNOWN_PREFIX:
            return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return ip


def blocked_reason(address: str, policy: SSRFPolicy) -> BlockedCategory | None:
    """
    Classify a raw IP string against ``policy``.

    :return: the category that forbids the address, ``None`` when it is allowed.
    """
    if "%" in address:
        address = address.split("%", 1)[0]
    ip = _unwrap_embedded_ipv4(ipaddress.ip_address(address))

    if ip.is_multicast:
        return BlockedCategory.MULTICAST
    if ip.is_unspecified:
        return BlockedCategory.UNSPECIFIED

    if ip.is_loopback:
        return None if policy.allow_loopback else BlockedCategory.LOOPBACK
    if ip.is_link_local:
        return None if policy.allow_link_local else BlockedCategory.LINK_LOCAL
    if ip.is_reserved:
        return None if policy.allow_reserved else BlockedCategory.RESERVED
    if ip.is_private or not ip.is_global or (ip.version == 6 and ip.is_site_local):
        return None if policy.allow_private else BlockedCategory.PRIVATE

    return None


def _host_label(host: bytes | str | None) -> str:
    if host is None:
        return "<unknown>"
    if isinstance(host, bytes):
        return host.decode("ascii", errors="replace")
    return host


def _filter_addrinfo(
    host: bytes | str | None,
    records: Sequence[_AddrInfo],
    policy: SSRFPolicy,
) -> list[_AddrInfo]:
    """Keep allowed candidates; raise if every resolved IP is forbidden."""
    kept: list[_AddrInfo] = []
    blocked: BlockedAddressError | None = None
    label = _host_label(host)
    for record in records:
        ip = record[4][0]
        try:
            reason = blocked_reason(ip, policy)
        except ValueError:
            blocked = BlockedAddressError(
                f"{label} resolves to an unparseable address ({ip})"
            )
            continue
        if reason is not None:
            blocked = BlockedAddressError(
                f"{label} resolves to a blocked {reason.value} ({ip})"
            )
            continue
        kept.append(record)
    if not kept and blocked is not None:
        raise blocked
    return kept


def _reject_scheme_and_proxies(
    request: PreparedRequest | Request,
    policy: SSRFPolicy,
    session_proxies: Mapping[str, str],
    trust_env: bool,
    kwargs: dict[str, Any],
) -> None:
    """Refuse disallowed schemes and any proxy (env or explicit). Mutates kwargs."""
    scheme = urlsplit(request.url or "").scheme.lower()
    if scheme not in policy.allowed_schemes:
        raise BlockedAddressError(f"scheme {scheme!r} is not allowed")

    if "proxies" not in kwargs:
        proxies = resolve_proxies(request, dict(session_proxies), trust_env)
    else:
        proxies = kwargs["proxies"] or {}

    for proxy in proxies.values():
        if proxy:
            raise BlockedAddressError(
                f"refusing to reach {proxy}: the SSRF guard does not cover "
                "proxied connections"
            )
    kwargs["proxies"] = {}


def _refuse_proxy(proxy: str, **_proxy_kwargs: Any) -> None:
    raise BlockedAddressError(
        f"refusing to reach {proxy}: the SSRF guard does not cover proxied connections"
    )


def _harden_adapters(session: niquests.Session) -> None:
    session.adapters.pop("http+unix://", None)
    for adapter in session.adapters.values():
        setattr(adapter, "proxy_manager_for", _refuse_proxy)


class _GuardedResolver(BaseResolver):
    """System (or other) resolver whose ``getaddrinfo`` drops forbidden IPs."""

    protocol = ProtocolResolver.CUSTOM
    implementation = "ssrf-guard"

    def __init__(self, inner: BaseResolver, policy: SSRFPolicy) -> None:
        super().__init__(None, None)
        self._inner = inner
        self.policy = policy

    def recycle(self) -> BaseResolver:
        recycled = self._inner.recycle()
        if recycled is self._inner:
            return self
        return _GuardedResolver(recycled, self.policy)

    def close(self) -> None:
        self._inner.close()

    def is_available(self) -> bool:
        return self._inner.is_available()

    def support(self, hostname: str | bytes | None) -> bool | None:
        return self._inner.support(hostname)

    def getaddrinfo(
        self,
        host: bytes | str | None,
        port: str | int | None,
        family: socket.AddressFamily,
        type: socket.SocketKind,
        proto: int = 0,
        flags: int = 0,
        *,
        quic_upgrade_via_dns_rr: bool = False,
    ) -> list[_AddrInfo]:
        records = self._inner.getaddrinfo(
            host,
            port,
            family,
            type,
            proto,
            flags,
            quic_upgrade_via_dns_rr=quic_upgrade_via_dns_rr,
        )
        return _filter_addrinfo(host, records, self.policy)


class _GuardedAsyncResolver(AsyncBaseResolver):
    """Async counterpart of :class:`_GuardedResolver`."""

    protocol = ProtocolResolver.CUSTOM
    implementation = "ssrf-guard"

    def __init__(self, inner: AsyncBaseResolver, policy: SSRFPolicy) -> None:
        super().__init__(None, None)
        self._inner = inner
        self.policy = policy

    def recycle(self) -> AsyncBaseResolver:
        recycled = self._inner.recycle()
        if recycled is self._inner:
            return self
        return _GuardedAsyncResolver(recycled, self.policy)

    async def close(self) -> None:
        await self._inner.close()

    def is_available(self) -> bool:
        return self._inner.is_available()

    def support(self, hostname: str | bytes | None) -> bool | None:
        return self._inner.support(hostname)

    async def getaddrinfo(
        self,
        host: bytes | str | None,
        port: str | int | None,
        family: socket.AddressFamily,
        type: socket.SocketKind,
        proto: int = 0,
        flags: int = 0,
        *,
        quic_upgrade_via_dns_rr: bool = False,
    ) -> list[_AddrInfo]:
        records = await self._inner.getaddrinfo(
            host,
            port,
            family,
            type,
            proto,
            flags,
            quic_upgrade_via_dns_rr=quic_upgrade_via_dns_rr,
        )
        return _filter_addrinfo(host, records, self.policy)


class SSRFProtectedSession(niquests.Session):
    """niquests Session that only reaches destinations allowed by ``policy``."""

    def __init__(self, policy: SSRFPolicy | None = None, **kwargs: Any) -> None:
        self.policy = policy or SSRFPolicy()
        kwargs["resolver"] = _GuardedResolver(create_resolver(None), self.policy)
        kwargs.setdefault("happy_eyeballs", False)
        super().__init__(**kwargs)
        self._own_resolver = True
        _harden_adapters(self)

    def send(self, request: PreparedRequest, **kwargs: Any) -> niquests.Response:
        _reject_scheme_and_proxies(
            request, self.policy, self.proxies, self.trust_env, kwargs
        )
        return super().send(request, **kwargs)


class SSRFProtectedAsyncSession(niquests.AsyncSession):
    """Async niquests Session that only reaches destinations allowed by ``policy``."""

    def __init__(self, policy: SSRFPolicy | None = None, **kwargs: Any) -> None:
        self.policy = policy or SSRFPolicy()
        kwargs["resolver"] = _GuardedAsyncResolver(
            create_async_resolver(None), self.policy
        )
        kwargs.setdefault("happy_eyeballs", False)
        super().__init__(**kwargs)
        self._own_resolver = True
        _harden_adapters(self)

    async def send(self, request: PreparedRequest, **kwargs: Any) -> Any:
        _reject_scheme_and_proxies(
            request, self.policy, self.proxies, self.trust_env, kwargs
        )
        return await super().send(request, **kwargs)
