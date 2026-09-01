"""
SSRF-hardened async HTTP client for producer-supplied URLs.

Validating the URL string before ``get`` is not enough (DNS rebinding, IPv6
encodings, redirects). Destination IPs are checked at connect time: niquests
resolves then connects to those records with no second lookup, so filtering
``getaddrinfo`` closes the rebinding window. Redirect hops are re-checked.

By default only public http(s) is allowed (no loopback, private, or link-local).
Catalog, Tabular and Metrics stay on plain niquests sessions.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit

import niquests
from niquests.models import PreparedRequest
from niquests.utils import create_async_resolver, resolve_proxies
from urllib3.contrib.resolver import ProtocolResolver
from urllib3.contrib.resolver._async import AsyncBaseResolver

from helpers.user_agent import USER_AGENT

_AddrInfo = tuple[
    socket.AddressFamily,
    socket.SocketKind,
    int,
    str | bytes,
    tuple[str, int] | tuple[str, int, int, int],
]

_NAT64_WELL_KNOWN_PREFIX = ipaddress.IPv6Network("64:ff9b::/96")
_IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


class BlockedCategory(StrEnum):
    MULTICAST = "multicast address"
    UNSPECIFIED = "unspecified address"
    LOOPBACK = "loopback address"
    LINK_LOCAL = "link-local address"
    PRIVATE = "private address"
    RESERVED = "reserved address"


class BlockedAddressError(Exception):
    """Raised for a destination forbidden by the policy. Not an ``OSError`` (urllib3 retries those)."""


@dataclass(frozen=True)
class SSRFPolicy:
    allow_loopback: bool = False
    allow_private: bool = False
    allow_link_local: bool = False
    allow_reserved: bool = False
    allowed_schemes: frozenset[str] = frozenset({"http", "https"})


def ssrf_policy() -> SSRFPolicy:
    """Build the policy from ``URLS_ALLOW_LOCAL`` / ``URLS_ALLOW_PRIVATE`` (private also covers link-local and reserved)."""
    local = _env_flag("URLS_ALLOW_LOCAL")
    private = _env_flag("URLS_ALLOW_PRIVATE")
    return SSRFPolicy(
        allow_loopback=local,
        allow_private=private,
        allow_link_local=private,
        allow_reserved=private,
    )


def ssrf_async_session(**kwargs: Any) -> SSRFProtectedAsyncSession:
    kwargs.setdefault("headers", {"User-Agent": USER_AGENT})
    return SSRFProtectedAsyncSession(ssrf_policy(), **kwargs)


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _unwrap_embedded_ipv4(ip: _IPAddress) -> _IPAddress:
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
    if "%" in address:
        address = address.split("%", 1)[0]
    ip = _unwrap_embedded_ipv4(ipaddress.ip_address(address))

    if ip.is_multicast:
        return BlockedCategory.MULTICAST
    if ip.is_unspecified:
        return BlockedCategory.UNSPECIFIED
    # Narrow categories first: loopback/link-local/reserved also report is_private.
    if ip.is_loopback:
        return None if policy.allow_loopback else BlockedCategory.LOOPBACK
    if ip.is_link_local:
        return None if policy.allow_link_local else BlockedCategory.LINK_LOCAL
    if ip.is_reserved:
        return None if policy.allow_reserved else BlockedCategory.RESERVED
    # is_private misses CGNAT; IPv6 site-local is neither private nor reserved.
    if ip.is_private or not ip.is_global or (ip.version == 6 and ip.is_site_local):
        return None if policy.allow_private else BlockedCategory.PRIVATE
    return None


def _filter_addrinfo(
    host: bytes | str | None,
    records: Sequence[_AddrInfo],
    policy: SSRFPolicy,
) -> list[_AddrInfo]:
    if host is None:
        label = "<unknown>"
    elif isinstance(host, bytes):
        label = host.decode("ascii", errors="replace")
    else:
        label = host

    kept: list[_AddrInfo] = []
    blocked: BlockedAddressError | None = None
    for record in records:
        ip = record[4][0]
        try:
            reason = blocked_reason(ip, policy)
        except ValueError:
            blocked = BlockedAddressError(
                f"{label} resolves to a blocked address ({ip})"
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


class _GuardedAsyncResolver(AsyncBaseResolver):
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


class SSRFProtectedAsyncSession(niquests.AsyncSession):
    """Async session: http(s) only, IP checked at connect, proxies refused, redirects re-checked."""

    def __init__(self, policy: SSRFPolicy | None = None, **kwargs: Any) -> None:
        self.policy = policy or SSRFPolicy()
        kwargs["resolver"] = _GuardedAsyncResolver(
            create_async_resolver(None), self.policy
        )
        kwargs.setdefault("happy_eyeballs", False)
        super().__init__(**kwargs)
        self._own_resolver = True
        self.adapters.pop("http+unix://", None)

    async def send(self, request: PreparedRequest, **kwargs: Any) -> Any:
        scheme = urlsplit(request.url or "").scheme.lower()
        if scheme not in self.policy.allowed_schemes:
            raise BlockedAddressError(f"scheme {scheme!r} is not allowed")

        if "proxies" not in kwargs:
            proxies = resolve_proxies(request, dict(self.proxies), self.trust_env)
        else:
            proxies = kwargs["proxies"] or {}
        proxy = _proxy_url(proxies)
        if proxy:
            raise BlockedAddressError(
                f"refusing to reach {proxy}: the SSRF guard does not cover "
                "proxied connections"
            )
        kwargs["proxies"] = {}
        return await super().send(request, **kwargs)


def _proxy_url(proxies: dict[str, Any]) -> str | None:
    """Return a configured proxy URL, ignoring NO_PROXY bypass lists."""
    for key, value in proxies.items():
        if key.lower() in {"no", "no_proxy"}:
            continue
        if value:
            return str(value)
    return None
