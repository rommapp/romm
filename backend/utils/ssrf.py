"""SSRF defense for outbound HTTP.

Two layers, both wired onto every httpx client built by `utils.context`:

  1. `validate_url_for_http_request` — a syntactic fast-fail check
     installed as an httpx request event hook. Rejects non-HTTP schemes,
     literal IPs in forbidden ranges (including non-standard IPv4 forms),
     reserved hostnames, and internal TLDs before any socket opens.

  2. `SSRFProtectedAsyncBackend` / `SSRFProtectedSyncBackend` — custom
     httpcore network backends that resolve the hostname inside
     `connect_tcp`, reject any address in a private/loopback/link-local/
     reserved/multicast/unspecified range, then connect to that *same*
     validated address. This is what defeats DNS rebinding: the address
     used by the OS for the TCP connection is the one we just checked,
     not a fresh lookup the attacker can answer differently. Doing this
     work in the backend also avoids blocking the event loop, since the
     async variant uses `loop.getaddrinfo`.

httpcore calls `start_tls(server_hostname=<URL host>)` after
`connect_tcp` returns, so TLS SNI and certificate verification still
use the original hostname even though we connect by IP.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import typing
from urllib.parse import urlparse

import httpcore
from httpcore._backends.auto import AutoBackend
from httpcore._backends.base import (
    SOCKET_OPTION,
    AsyncNetworkBackend,
    AsyncNetworkStream,
    NetworkBackend,
    NetworkStream,
)
from httpcore._backends.sync import SyncBackend

from logger.logger import log
from utils.validation import ValidationError

# RFC 6052 well-known NAT64 prefix. DNS64 resolvers embed a public IPv4 in
# the low 32 bits so IPv6-only clients can reach IPv4-only hosts. We must
# judge such an address by its embedded IPv4, not the (reserved) wrapper.
_NAT64_WELL_KNOWN_PREFIX = ipaddress.ip_network("64:ff9b::/96")


def _nat64_embedded_ipv4(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> ipaddress.IPv4Address | None:
    """Return the IPv4 embedded in a well-known NAT64 address, else None."""
    if isinstance(ip, ipaddress.IPv6Address) and ip in _NAT64_WELL_KNOWN_PREFIX:
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return None


def is_forbidden_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True if the IP must not be reached from a server-side HTTP request."""
    embedded = _nat64_embedded_ipv4(ip)
    if embedded is not None:
        # A NAT64-wrapped public IPv4 is a legitimate destination on DNS64
        # networks; a wrapped private/internal IPv4 must still be blocked.
        return is_forbidden_ip(embedded)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
        or not ip.is_global
    )


def parse_ip_literal(
    host: str,
) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Return the parsed IP if `host` is a literal address, else None.

    Accepts non-standard IPv4 forms (hex, decimal, shorthand) via
    `socket.inet_aton`, which is what HTTP clients themselves accept.
    """
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    try:
        packed = socket.inet_aton(host)
    except OSError:
        return None
    return ipaddress.IPv4Address(packed)


def _pick_safe_address(addr_infos: typing.Iterable[typing.Any], host: str) -> str:
    """Validate every resolved address and return the literal IP to connect to.

    All returned addresses are checked: if any falls in a forbidden range
    we reject the whole name, rather than just skipping that record. A
    malicious DNS server can otherwise mix public and private answers
    and rely on the client to round-robin.
    """
    chosen: str | None = None
    for *_, sockaddr in addr_infos:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except (ValueError, IndexError):
            continue
        if is_forbidden_ip(ip):
            msg = (
                f"SSRF prevention: hostname {host!r} resolves to forbidden " f"IP {ip}"
            )
            log.error(msg)
            raise httpcore.ConnectError(msg)
        if chosen is None:
            chosen = sockaddr[0]
    if chosen is None:
        raise httpcore.ConnectError(f"No usable addresses for {host!r}")
    return chosen


def _check_literal(host: str) -> bool:
    """Return True if `host` is a literal IP that has been validated as safe.

    Raises httpcore.ConnectError if it is a literal IP in a forbidden range.
    Returns False if `host` is a hostname (caller must resolve and validate).
    """
    literal = parse_ip_literal(host)
    if literal is None:
        return False
    if is_forbidden_ip(literal):
        msg = f"SSRF prevention: connection to forbidden IP {literal}"
        log.error(msg)
        raise httpcore.ConnectError(msg)
    return True


class SSRFProtectedAsyncBackend(AsyncNetworkBackend):
    """Async backend that validates resolved IPs before establishing TCP."""

    def __init__(self, inner: AsyncNetworkBackend | None = None) -> None:
        self._inner = inner or AutoBackend()

    # `timeout` parameter is required by AsyncNetworkBackend.connect_tcp;
    # ruff/ASYNC109 advises against timeout parameters on async APIs *we*
    # author, but we are implementing an external interface here. The
    # timeout is consumed via `asyncio.timeout()` below, which is the
    # asyncio-native pattern ASYNC109 endorses.
    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,  # noqa: ASYNC109
        local_address: str | None = None,
        socket_options: typing.Iterable[SOCKET_OPTION] | None = None,
    ) -> AsyncNetworkStream:
        """Validate the resolved IP, then connect via the inner backend.

        The DNS lookup is wrapped in `asyncio.timeout()` so a slow
        resolver is bounded by the caller's timeout. The previous code
        only timed out the TCP connect inside the inner backend, leaving
        `loop.getaddrinfo` unbounded.
        """
        if _check_literal(host):
            return await self._inner.connect_tcp(
                host, port, timeout, local_address, socket_options
            )

        loop = asyncio.get_running_loop()
        try:
            async with asyncio.timeout(timeout):
                addr_infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise httpcore.ConnectError(
                f"DNS resolution failed for {host!r}: {exc}"
            ) from exc
        except TimeoutError as exc:
            raise httpcore.ConnectTimeout(
                f"DNS resolution timed out for {host!r}"
            ) from exc

        pinned_ip = _pick_safe_address(addr_infos, host)
        return await self._inner.connect_tcp(
            pinned_ip, port, timeout, local_address, socket_options
        )

    # See note on connect_tcp re: ASYNC109 / interface implementation.
    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,  # noqa: ASYNC109
        socket_options: typing.Iterable[SOCKET_OPTION] | None = None,
    ) -> AsyncNetworkStream:
        return await self._inner.connect_unix_socket(path, timeout, socket_options)

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


class SSRFProtectedSyncBackend(NetworkBackend):
    """Sync backend that validates resolved IPs before establishing TCP."""

    def __init__(self, inner: NetworkBackend | None = None) -> None:
        self._inner = inner if inner is not None else SyncBackend()

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: typing.Iterable[SOCKET_OPTION] | None = None,
    ) -> NetworkStream:
        if _check_literal(host):
            return self._inner.connect_tcp(
                host, port, timeout, local_address, socket_options
            )

        try:
            addr_infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise httpcore.ConnectError(
                f"DNS resolution failed for {host!r}: {exc}"
            ) from exc

        pinned_ip = _pick_safe_address(addr_infos, host)
        return self._inner.connect_tcp(
            pinned_ip, port, timeout, local_address, socket_options
        )

    def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: typing.Iterable[SOCKET_OPTION] | None = None,
    ) -> NetworkStream:
        return self._inner.connect_unix_socket(path, timeout, socket_options)


def install_async_ssrf_protection(client: typing.Any) -> None:
    """Wrap the client's default transport so SSRF validation runs at connect time.

    httpx does not expose `network_backend` through its public transport
    API, so we mutate `_pool._network_backend` after construction.
    """
    pool = client._transport._pool
    if not isinstance(pool._network_backend, SSRFProtectedAsyncBackend):
        pool._network_backend = SSRFProtectedAsyncBackend(inner=pool._network_backend)


def install_sync_ssrf_protection(client: typing.Any) -> None:
    """Sync counterpart of `install_async_ssrf_protection`."""
    pool = client._transport._pool
    if not isinstance(pool._network_backend, SSRFProtectedSyncBackend):
        pool._network_backend = SSRFProtectedSyncBackend(inner=pool._network_backend)


RESERVED_HOSTNAMES = [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",  # trunk-ignore(bandit/B104)
    "::1",
    "::",
]


def validate_url_for_http_request(url: str, field_name: str = "URL") -> None:
    """Syntactically validate a URL before passing it to an HTTP client.

    Fast-fail check for cases that don't need DNS to detect:

    - The URL scheme is http or https only
    - If the host is a literal IP address, it is not private/internal/reserved
    - The host is not a reserved hostname (localhost, 127.0.0.1, etc.)
    - The host does not use internal TLDs (.local, .internal, .localhost)

    Wired in as an httpx request event hook by `utils.context.create_httpx_*`,
    so every request that goes through a context-provided client runs this
    automatically — direct calls from feature code are not required.

    Dynamic SSRF protection (rejecting hostnames that resolve to a private
    IP, including DNS-rebinding names like `127.0.0.1.nip.io`) happens
    inside the HTTP client's connect path via the backends above. Doing
    the DNS check here would (a) be defeated by DNS rebinding because
    httpx re-resolves at connect time, and (b) block the event loop,
    since `socket.getaddrinfo` is synchronous and most callers are async.

    Args:
        url (str): The URL to validate
        field_name (str): The name of the field for error messages

    Raises:
        ValidationError: If the URL is syntactically invalid or matches one
            of the static SSRF deny patterns.
    """
    if not url or not url.strip():
        msg = f"{field_name} cannot be empty"
        log.error(msg)
        raise ValidationError(msg, field_name)

    try:
        parsed = urlparse(url)
    except Exception as e:
        msg = f"Invalid {field_name}: unable to parse URL"
        log.error(f"{msg}: {str(e)}")
        raise ValidationError(msg, field_name) from e

    # Validate scheme - only allow http and https
    if parsed.scheme not in ["http", "https"]:
        msg = f"Invalid {field_name}: only http and https schemes are allowed"
        log.error(f"SSRF prevention: {msg} - got scheme '{parsed.scheme}'")
        raise ValidationError(msg, field_name)

    # Extract hostname
    hostname = parsed.hostname
    if not hostname:
        msg = f"Invalid {field_name}: missing hostname"
        log.error(msg)
        raise ValidationError(msg, field_name)

    # Block reserved hostnames that are commonly used to refer to internal services.
    if hostname.lower() in RESERVED_HOSTNAMES:
        msg = f"Invalid {field_name}: localhost and reserved hostnames are not allowed"
        log.error(f"SSRF prevention: {msg} - hostname '{hostname}'")
        raise ValidationError(msg, field_name)

    # Try to parse hostname as a literal IP (standard or non-standard form).
    # HTTP clients accept hex (0x7f000001), decimal (2130706433), and
    # shorthand-dotted (127.1) integers via inet_aton, so we mirror that.
    ip = parse_ip_literal(hostname)
    if ip is not None:
        if is_forbidden_ip(ip):
            msg = (
                f"Invalid {field_name}: private, internal, reserved, "
                "or multicast IP addresses are not allowed"
            )
            log.error(f"SSRF prevention: {msg} - IP '{ip}'")
            raise ValidationError(msg, field_name)
        return

    # Block common internal TLDs
    hostname_lower = hostname.lower()
    internal_tlds = [".local", ".internal", ".localhost"]
    if any(hostname_lower.endswith(tld) for tld in internal_tlds):
        msg = f"Invalid {field_name}: internal domain names are not allowed"
        log.error(f"SSRF prevention: {msg} - hostname '{hostname}'")
        raise ValidationError(msg, field_name)
