"""Tests for SSRF defense: URL validator + httpcore network backends."""

import asyncio
import ipaddress
import socket
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpcore
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from utils.ssrf import (
    SSRFProtectedAsyncBackend,
    SSRFProtectedSyncBackend,
    _parse_origin,
    is_forbidden_ip,
    parse_ip_literal,
    validate_url_for_http_request,
)
from utils.validation import ValidationError

ConnectCall = tuple[tuple[Any, ...], dict[str, Any]]


def _addr_info(ip: str, port: int) -> list[tuple[Any, ...]]:
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    return [(family, socket.SOCK_STREAM, 0, "", (ip, port))]


def _stub_async_inner(connect_calls: list[ConnectCall]) -> MagicMock:
    inner = MagicMock()

    def _record(*args: Any, **kwargs: Any) -> MagicMock:
        connect_calls.append((args, kwargs))
        return MagicMock()

    inner.connect_tcp = AsyncMock(side_effect=_record)
    return inner


def _stub_sync_inner(connect_calls: list[ConnectCall]) -> MagicMock:
    inner = MagicMock()

    def _record(*args: Any, **kwargs: Any) -> MagicMock:
        connect_calls.append((args, kwargs))
        return MagicMock()

    inner.connect_tcp = MagicMock(side_effect=_record)
    return inner


class TestIsForbiddenIp:
    @pytest.mark.parametrize(
        "ip",
        [
            "127.0.0.1",
            "10.0.0.1",
            "192.168.1.1",
            "172.16.0.1",
            "169.254.169.254",
            "0.0.0.0",
            "224.0.0.1",
            "::1",
            "fc00::1",
            "fe80::1",
            "ff02::1",
            # NAT64-wrapped internal IPv4 must stay blocked (embedded IPv4 checked).
            "64:ff9b::7f00:1",  # 127.0.0.1 loopback
            "64:ff9b::a00:1",  # 10.0.0.1 private
            "64:ff9b::c0a8:101",  # 192.168.1.1 private
            "64:ff9b::a9fe:a9fe",  # 169.254.169.254 cloud metadata
            # RFC 8215 local-use NAT64 prefix is private; not unwrapped, stays blocked.
            "64:ff9b:1::8d5f:accd",
        ],
    )
    def test_forbidden(self, ip):
        assert is_forbidden_ip(ipaddress.ip_address(ip)) is True

    @pytest.mark.parametrize(
        "ip",
        [
            "8.8.8.8",
            "1.1.1.1",
            "93.184.216.34",
            "2001:4860:4860::8888",
            # NAT64-wrapped public IPv4 (DNS64) must be allowed. See issue #3668.
            "64:ff9b::8d5f:accd",  # 141.95.172.205
            "64:ff9b::808:808",  # 8.8.8.8
        ],
    )
    def test_allowed(self, ip):
        assert is_forbidden_ip(ipaddress.ip_address(ip)) is False


class TestParseIpLiteral:
    def test_standard(self):
        assert str(parse_ip_literal("127.0.0.1")) == "127.0.0.1"
        assert str(parse_ip_literal("::1")) == "::1"

    def test_non_standard_ipv4(self):
        # Hex, decimal, shorthand - all map to 127.0.0.1
        assert str(parse_ip_literal("0x7f000001")) == "127.0.0.1"
        assert str(parse_ip_literal("2130706433")) == "127.0.0.1"
        assert str(parse_ip_literal("127.1")) == "127.0.0.1"

    def test_hostname_returns_none(self):
        assert parse_ip_literal("example.com") is None


class TestSSRFProtectedAsyncBackend:
    async def test_safe_hostname_connects_to_pinned_ip(self, monkeypatch):
        """Backend resolves once, validates, and passes the pinned IP to inner."""
        calls: list[ConnectCall] = []
        inner = _stub_async_inner(calls)
        backend = SSRFProtectedAsyncBackend(inner=inner)

        async def fake_getaddrinfo(host, port, *args, **kwargs):
            return _addr_info("93.184.216.34", port)

        loop = asyncio.get_running_loop()
        monkeypatch.setattr(loop, "getaddrinfo", fake_getaddrinfo)

        await backend.connect_tcp("example.com", 443)

        # inner must receive the resolved IP, not the original hostname.
        # That is what pins the address against DNS rebinding.
        assert calls[0][0][0] == "93.184.216.34"
        assert calls[0][0][1] == 443

    async def test_nat64_wrapped_public_ip_connects(self, monkeypatch):
        """DNS64 case (issue #3668): a NAT64-wrapped public IPv4 must be reachable."""
        calls: list[ConnectCall] = []
        inner = _stub_async_inner(calls)
        backend = SSRFProtectedAsyncBackend(inner=inner)

        async def fake_getaddrinfo(host, port, *args, **kwargs):
            return _addr_info("64:ff9b::8d5f:accd", port)  # wraps 141.95.172.205

        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", fake_getaddrinfo)

        await backend.connect_tcp("neoclone.screenscraper.fr", 443)

        assert calls[0][0][0] == "64:ff9b::8d5f:accd"
        assert calls[0][0][1] == 443

    async def test_nat64_wrapped_private_ip_is_rejected(self, monkeypatch):
        """A NAT64-wrapped private/loopback IPv4 must still be blocked."""
        inner = _stub_async_inner([])
        backend = SSRFProtectedAsyncBackend(inner=inner)

        async def fake_getaddrinfo(host, port, *args, **kwargs):
            return _addr_info("64:ff9b::7f00:1", port)  # wraps 127.0.0.1

        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", fake_getaddrinfo)

        with pytest.raises(httpcore.ConnectError, match="forbidden IP"):
            await backend.connect_tcp("nat64.rebind.example.com", 80)
        inner.connect_tcp.assert_not_called()

    async def test_hostname_resolving_to_private_ip_is_rejected(self, monkeypatch):
        """DNS rebinding case: hostname resolves to 127.0.0.1 must fail."""
        inner = _stub_async_inner([])
        backend = SSRFProtectedAsyncBackend(inner=inner)

        async def fake_getaddrinfo(host, port, *args, **kwargs):
            return _addr_info("127.0.0.1", port)

        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", fake_getaddrinfo)

        with pytest.raises(httpcore.ConnectError, match="forbidden IP"):
            await backend.connect_tcp("127.0.0.1.nip.io", 80)
        inner.connect_tcp.assert_not_called()

    async def test_mixed_resolution_rejected(self, monkeypatch):
        """If any returned address is forbidden, reject - don't trust round-robin."""
        inner = _stub_async_inner([])
        backend = SSRFProtectedAsyncBackend(inner=inner)

        async def fake_getaddrinfo(host, port, *args, **kwargs):
            return _addr_info("93.184.216.34", port) + _addr_info("10.0.0.1", port)

        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", fake_getaddrinfo)

        with pytest.raises(httpcore.ConnectError, match="forbidden IP"):
            await backend.connect_tcp("mixed.example.com", 80)
        inner.connect_tcp.assert_not_called()

    async def test_literal_forbidden_ip_rejected(self):
        inner = _stub_async_inner([])
        backend = SSRFProtectedAsyncBackend(inner=inner)
        with pytest.raises(httpcore.ConnectError, match="forbidden IP"):
            await backend.connect_tcp("169.254.169.254", 80)
        inner.connect_tcp.assert_not_called()

    async def test_literal_public_ip_passes_through(self):
        calls: list[ConnectCall] = []
        inner = _stub_async_inner(calls)
        backend = SSRFProtectedAsyncBackend(inner=inner)
        await backend.connect_tcp("8.8.8.8", 443)
        # Literal public IPs are passed through unchanged.
        assert calls[0][0][0] == "8.8.8.8"

    async def test_non_standard_ipv4_literal_blocked(self):
        """Hex/decimal IPv4 forms must be blocked, matching httpx's parsing."""
        inner = _stub_async_inner([])
        backend = SSRFProtectedAsyncBackend(inner=inner)
        with pytest.raises(httpcore.ConnectError, match="forbidden IP"):
            await backend.connect_tcp("2130706433", 80)  # 127.0.0.1
        inner.connect_tcp.assert_not_called()

    async def test_dns_timeout_raises_connect_timeout(self, monkeypatch):
        """A resolver that hangs past the caller's timeout must not block forever.

        Regression: an earlier version applied the caller's timeout only to
        the TCP connect inside the inner backend, leaving `loop.getaddrinfo`
        unbounded. We now wrap the lookup in `asyncio.timeout()` so a slow
        resolver is bounded by the same budget the caller specified.
        """
        inner = _stub_async_inner([])
        backend = SSRFProtectedAsyncBackend(inner=inner)

        async def hang_forever(*args, **kwargs):
            await asyncio.sleep(3600)

        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", hang_forever)

        with pytest.raises(httpcore.ConnectTimeout, match="DNS resolution timed out"):
            await backend.connect_tcp("slow.example.com", 80, timeout=0.05)
        inner.connect_tcp.assert_not_called()

    async def test_dns_failure_propagates_as_connect_error(self, monkeypatch):
        inner = _stub_async_inner([])
        backend = SSRFProtectedAsyncBackend(inner=inner)

        async def fake_getaddrinfo(*args, **kwargs):
            raise socket.gaierror("Name or service not known")

        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", fake_getaddrinfo)

        with pytest.raises(httpcore.ConnectError, match="DNS resolution failed"):
            await backend.connect_tcp("nonexistent.invalid", 80)
        inner.connect_tcp.assert_not_called()


class TestSSRFProtectedSyncBackend:
    def test_safe_hostname_connects_to_pinned_ip(self, monkeypatch):
        calls: list[ConnectCall] = []
        inner = _stub_sync_inner(calls)
        backend = SSRFProtectedSyncBackend(inner=inner)

        monkeypatch.setattr(
            socket,
            "getaddrinfo",
            lambda host, port, *a, **kw: _addr_info("93.184.216.34", port),
        )

        backend.connect_tcp("example.com", 443)
        assert calls[0][0][0] == "93.184.216.34"

    def test_hostname_resolving_to_private_ip_is_rejected(self, monkeypatch):
        inner = _stub_sync_inner([])
        backend = SSRFProtectedSyncBackend(inner=inner)
        monkeypatch.setattr(
            socket,
            "getaddrinfo",
            lambda host, port, *a, **kw: _addr_info("127.0.0.1", port),
        )
        with pytest.raises(httpcore.ConnectError, match="forbidden IP"):
            backend.connect_tcp("127.0.0.1.nip.io", 80)
        inner.connect_tcp.assert_not_called()

    def test_literal_forbidden_ip_rejected(self):
        inner = _stub_sync_inner([])
        backend = SSRFProtectedSyncBackend(inner=inner)
        with pytest.raises(httpcore.ConnectError, match="forbidden IP"):
            backend.connect_tcp("10.0.0.1", 80)
        inner.connect_tcp.assert_not_called()


class TestInternalOriginAllowlist:
    """Admin-configured origins (e.g. self-hosted Playmatch) bypass SSRF checks,
    but only for the exact host:port that was trusted."""

    def test_parse_origin_normalizes(self):
        assert _parse_origin("http://playmatch:8000/api/v2") == ("playmatch", 8000)
        assert _parse_origin("https://pm.example.com/api") == ("pm.example.com", 443)
        assert _parse_origin("http://LAN-HOST/") == ("lan-host", 80)

    def test_parse_origin_rejects_invalid(self):
        assert _parse_origin("") is None  # empty is skipped
        assert _parse_origin("ftp://nope") is None  # non-http scheme is skipped

    async def test_async_allowlisted_ip_connects_without_validation(self):
        """A trusted private LAN IP:port connects directly, no rebinding check."""
        calls: list[ConnectCall] = []
        inner = _stub_async_inner(calls)
        backend = SSRFProtectedAsyncBackend(
            inner=inner, allowlist=frozenset({("192.168.1.50", 8000)})
        )

        await backend.connect_tcp("192.168.1.50", 8000)

        assert calls[0][0][0] == "192.168.1.50"
        assert calls[0][0][1] == 8000

    async def test_async_allowlisted_hostname_connects_without_resolution(
        self, monkeypatch
    ):
        """A trusted Docker service name connects via the inner backend directly."""
        calls: list[ConnectCall] = []
        inner = _stub_async_inner(calls)
        backend = SSRFProtectedAsyncBackend(
            inner=inner, allowlist=frozenset({("playmatch", 8000)})
        )

        def _boom(*args, **kwargs):
            raise AssertionError("allowlisted host must not be resolved")

        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", _boom)

        await backend.connect_tcp("playmatch", 8000)

        assert calls[0][0][0] == "playmatch"

    async def test_async_allowlist_is_port_scoped(self, monkeypatch):
        """Same host on a non-trusted port still gets the full SSRF check."""
        inner = _stub_async_inner([])
        backend = SSRFProtectedAsyncBackend(
            inner=inner, allowlist=frozenset({("192.168.1.50", 8000)})
        )

        with pytest.raises(httpcore.ConnectError, match="forbidden IP"):
            await backend.connect_tcp("192.168.1.50", 9999)
        inner.connect_tcp.assert_not_called()

    def test_sync_allowlisted_ip_connects_without_validation(self):
        calls: list[ConnectCall] = []
        inner = _stub_sync_inner(calls)
        backend = SSRFProtectedSyncBackend(
            inner=inner, allowlist=frozenset({("192.168.1.50", 8000)})
        )

        backend.connect_tcp("192.168.1.50", 8000)

        assert calls[0][0][0] == "192.168.1.50"

    def test_validator_allows_trusted_lan_ip(self):
        """The static gate lets a trusted literal LAN IP:port through."""
        allow = frozenset({("192.168.1.50", 8000)})
        # Would raise without the allowlist (private IP literal).
        validate_url_for_http_request(
            "http://192.168.1.50:8000/health", allowlist=allow
        )
        with pytest.raises(ValidationError):
            validate_url_for_http_request(
                "http://192.168.1.50:8000/health", allowlist=frozenset()
            )

    def test_validator_allows_trusted_localhost(self):
        """The static gate lets a trusted localhost:port through despite the deny list."""
        allow = frozenset({("localhost", 8000)})
        validate_url_for_http_request("http://localhost:8000/health", allowlist=allow)
        with pytest.raises(ValidationError):
            validate_url_for_http_request(
                "http://localhost:8000/health", allowlist=frozenset()
            )


class TestRequestEventHook:
    """Verify the syntactic URL validator is wired as a request event hook.

    With the hook in place, every request through a context-provided client
    is validated automatically; feature code does not need to call
    `validate_url_for_http_request` itself.
    """

    async def test_async_hook_rejects_bad_scheme(self):
        from utils.context import create_httpx_async_client
        from utils.validation import ValidationError

        client = create_httpx_async_client()
        try:
            with pytest.raises(ValidationError, match="only http and https"):
                await client.get("file:///etc/passwd")
        finally:
            await client.aclose()

    async def test_async_hook_rejects_internal_tld(self):
        from utils.context import create_httpx_async_client
        from utils.validation import ValidationError

        client = create_httpx_async_client()
        try:
            with pytest.raises(ValidationError, match="internal domain names"):
                await client.get("http://printer.local/status")
        finally:
            await client.aclose()

    def test_sync_hook_rejects_literal_private_ip(self):
        from utils.context import create_httpx_client
        from utils.validation import ValidationError

        with create_httpx_client() as client:
            with pytest.raises(ValidationError, match="private, internal"):
                client.get("http://10.0.0.1/")


class TestInstallation:
    """Verify the backend is actually wired onto httpx clients we create."""

    def test_create_httpx_async_client_installs_backend(self):
        from utils.context import create_httpx_async_client
        from utils.ssrf import SSRFProtectedAsyncBackend as Async

        client = create_httpx_async_client()
        try:
            assert isinstance(client._transport._pool._network_backend, Async)
        finally:
            asyncio.run(client.aclose())

    def test_create_httpx_client_installs_backend(self):
        from utils.context import create_httpx_client
        from utils.ssrf import SSRFProtectedSyncBackend as Sync

        with create_httpx_client() as client:
            assert isinstance(client._transport._pool._network_backend, Sync)

    def test_proxy_transports_are_not_wrapped(self):
        """Proxy mounts must keep their stock backend.

        A common deployment pattern is `HTTPS_PROXY=http://sidecar:9050`,
        where `sidecar` resolves to a docker-bridge private IP. If we
        wrapped the proxy transport, our SSRF backend would refuse to
        connect to the operator's chosen proxy. SSRF protection at the
        proxy hop is the operator's responsibility; the destination URL
        is still validated by the request event hook on the client.
        """
        import httpx

        from utils.ssrf import SSRFProtectedAsyncBackend as Async
        from utils.ssrf import (
            install_async_ssrf_protection,
        )

        client = httpx.AsyncClient(proxy="http://proxy.invalid:3128")
        try:
            install_async_ssrf_protection(client)
            assert isinstance(client._transport._pool._network_backend, Async)
            for mount in client._mounts.values():
                if mount is None:
                    continue
                # Proxy mount must NOT have been wrapped.
                assert not isinstance(mount._pool._network_backend, Async)
        finally:
            asyncio.run(client.aclose())


class TestValidateUrlForHttpRequest:
    """Test URL validation for HTTP requests to prevent SSRF attacks."""

    def test_valid_http_urls(self):
        """Valid HTTP/HTTPS URLs pass syntactic validation without DNS lookups.

        DNS-based SSRF checks live in the HTTP client's connect path, so
        this layer must not call DNS.
        """
        validate_url_for_http_request("http://example.com", "test_url")
        validate_url_for_http_request("https://example.com", "test_url")
        validate_url_for_http_request("http://example.com/path", "test_url")
        validate_url_for_http_request("https://example.com/path?query=1", "test_url")
        validate_url_for_http_request("http://subdomain.example.com", "test_url")

    def test_validator_does_not_perform_dns_lookup(self, monkeypatch):
        """Regression: validator must not block the event loop on DNS.

        Earlier implementations called `socket.getaddrinfo`, which both
        blocked the running event loop in async media-download callers and
        was defeated by DNS rebinding (the value seen here did not match
        the IP httpx later connected to). We patch getaddrinfo to a poison
        function so any accidental reintroduction fails this test.
        """

        def _explode(*_args, **_kwargs):
            raise AssertionError(
                "validate_url_for_http_request must not call DNS; "
                "SSRF DNS protection lives in the HTTP client backend"
            )

        monkeypatch.setattr(socket, "getaddrinfo", _explode)
        validate_url_for_http_request("http://example.com", "test_url")

    def test_invalid_empty_url(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("", "test_url")
        assert "cannot be empty" in exc_info.value.message

    def test_invalid_scheme(self):
        for url in (
            "ftp://example.com",
            "file:///etc/passwd",
            "data:text/html,<h1>test</h1>",
            "javascript:alert(1)",  # XSS attack vector
        ):
            with pytest.raises(ValidationError) as exc_info:
                validate_url_for_http_request(url, "test_url")
            assert "only http and https schemes are allowed" in exc_info.value.message

    def test_invalid_localhost(self):
        for url in (
            "http://localhost",
            "http://127.0.0.1",
            "http://[::1]",
            "http://0.0.0.0",
        ):
            with pytest.raises(ValidationError) as exc_info:
                validate_url_for_http_request(url, "test_url")
            assert (
                "localhost and reserved hostnames are not allowed"
                in exc_info.value.message
            )

    def test_invalid_private_ipv4_addresses(self):
        for url in (
            "http://10.0.0.1",
            "http://192.168.1.1",
            "http://172.16.0.1",
            "http://172.31.255.254",
        ):
            with pytest.raises(ValidationError) as exc_info:
                validate_url_for_http_request(url, "test_url")
            assert (
                "private, internal, reserved, or multicast IP addresses are not allowed"
                in exc_info.value.message
            )

    def test_invalid_loopback_addresses(self):
        # 127.0.0.1 itself is in RESERVED_HOSTNAMES; these cover the rest of 127/8.
        for url in ("http://127.0.0.2", "http://127.255.255.255"):
            with pytest.raises(ValidationError) as exc_info:
                validate_url_for_http_request(url, "test_url")
            assert (
                "private, internal, reserved, or multicast IP addresses are not allowed"
                in exc_info.value.message
            )

    def test_invalid_private_ipv6_addresses(self):
        for url in (
            "http://[fe80::1]",  # link-local
            "http://[fc00::1]",  # unique local
            "http://[fd00::1]",  # unique local
        ):
            with pytest.raises(ValidationError) as exc_info:
                validate_url_for_http_request(url, "test_url")
            assert (
                "private, internal, reserved, or multicast IP addresses are not allowed"
                in exc_info.value.message
            )

    def test_invalid_multicast_addresses(self):
        for url in ("http://224.0.0.1", "http://[ff02::1]"):
            with pytest.raises(ValidationError) as exc_info:
                validate_url_for_http_request(url, "test_url")
            assert (
                "private, internal, reserved, or multicast IP addresses are not allowed"
                in exc_info.value.message
            )

    def test_invalid_internal_tlds(self):
        for url in (
            "http://server.local",
            "http://server.internal",
            "http://server.localhost",
        ):
            with pytest.raises(ValidationError) as exc_info:
                validate_url_for_http_request(url, "test_url")
            assert "internal domain names are not allowed" in exc_info.value.message

    def test_invalid_non_standard_ip_representations(self):
        """Non-standard IPv4 forms (hex, decimal, shorthand) are SSRF bypass vectors."""
        cases = [
            "http://0x7f000001",  # hex 127.0.0.1
            "http://2130706433",  # decimal 127.0.0.1
            "http://127.1",  # shorthand 127.0.0.1
            "http://0x0a000001",  # hex 10.0.0.1
            "http://3232235777",  # decimal 192.168.1.1
            "http://0xa9fea9fe",  # hex 169.254.169.254 (cloud metadata)
        ]
        for url in cases:
            with pytest.raises(ValidationError) as exc_info:
                validate_url_for_http_request(url, "test_url")
            assert (
                "private, internal, reserved, or multicast IP addresses are not allowed"
                in exc_info.value.message
            )

    def test_invalid_missing_hostname(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://", "test_url")
        assert "missing hostname" in exc_info.value.message


_LOWER_ALNUM = "abcdefghijklmnopqrstuvwxyz0123456789"
_LOWER = "abcdefghijklmnopqrstuvwxyz"


class TestValidateUrlProperties:
    """Property-based tests for the SSRF-prevention URL validator."""

    @given(st.ip_addresses(v=4))
    def test_globally_routable_ipv4_is_allowed(self, ip):
        # is_global already excludes private/loopback/link-local/reserved.
        assume(ip.is_global and not ip.is_multicast)
        # Should not raise.
        validate_url_for_http_request(f"http://{ip}/path")

    @given(st.ip_addresses(v=4))
    def test_internal_ipv4_is_always_blocked(self, ip):
        assume(ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast)
        with pytest.raises(ValidationError):
            validate_url_for_http_request(f"http://{ip}/")

    @given(st.ip_addresses(v=6))
    def test_internal_ipv6_is_always_blocked(self, ip):
        assume(ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast)
        with pytest.raises(ValidationError):
            validate_url_for_http_request(f"http://[{ip}]/")

    @given(st.text(alphabet=_LOWER, min_size=1, max_size=10))
    def test_non_http_scheme_is_always_blocked(self, scheme):
        assume(scheme not in ("http", "https"))
        with pytest.raises(ValidationError):
            validate_url_for_http_request(f"{scheme}://example.com/")

    @given(
        st.text(alphabet=_LOWER_ALNUM, min_size=1, max_size=20),
        st.sampled_from([".local", ".internal", ".localhost"]),
    )
    def test_internal_tld_is_always_blocked(self, label, tld):
        with pytest.raises(ValidationError):
            validate_url_for_http_request(f"http://{label}{tld}/")

    @given(st.text())
    def test_never_raises_unexpected_exception(self, url):
        # The validator must only ever signal failure via ValidationError,
        # never leak a parsing/socket error to the caller.
        try:
            validate_url_for_http_request(url)
        except ValidationError:
            pass
