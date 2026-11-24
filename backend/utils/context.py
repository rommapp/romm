import ssl
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar, Token
from functools import partial
from typing import TYPE_CHECKING, TypeVar

import aiohttp
import httpx2
from config import has_proxy_env

from utils.ssrf import (
    INTERNAL_ORIGIN_ALLOWLIST,
    install_async_ssrf_protection,
    install_sync_ssrf_protection,
    validate_url_for_http_request,
)

if TYPE_CHECKING:
    from fastapi import Request, Response

_T = TypeVar("_T")

ctx_aiohttp_session: ContextVar[aiohttp.ClientSession] = ContextVar("aiohttp_session")
ctx_httpx_client: ContextVar[httpx2.AsyncClient] = ContextVar("httpx_client")
# Sync callers cannot await the async client above, and opening a client per
# call throws away every connection it just made. This one is created once for
# the life of the app, and may only reach public addresses: everything the
# plugin system fetches is a URL somebody else supplied.
ctx_httpx_sync_client: ContextVar[httpx2.Client] = ContextVar("httpx_sync_client")


def _validate_request_url_sync(request: httpx2.Request) -> None:
    validate_url_for_http_request(str(request.url))


async def _validate_request_url_async(
    request: httpx2.Request, allowlist: frozenset[tuple[str, int]]
) -> None:
    validate_url_for_http_request(str(request.url), allowlist=allowlist)


def create_aiohttp_session() -> aiohttp.ClientSession:
    return aiohttp.ClientSession(trust_env=has_proxy_env())


def create_httpx_async_client(
    allowlist: frozenset[tuple[str, int]] = INTERNAL_ORIGIN_ALLOWLIST,
    verify: ssl.SSLContext | bool = True,
) -> httpx2.AsyncClient:
    """An SSRF-guarded client that lets only `allowlist` origins reach private addresses."""
    client = httpx2.AsyncClient(
        trust_env=has_proxy_env(),
        verify=verify,
        event_hooks={
            "request": [partial(_validate_request_url_async, allowlist=allowlist)]
        },
    )
    install_async_ssrf_protection(client, allowlist=allowlist)
    return client


def create_httpx_client(
    allowlist: frozenset[tuple[str, int]] = INTERNAL_ORIGIN_ALLOWLIST,
) -> httpx2.Client:
    """An SSRF-guarded client that lets only `allowlist` origins reach private addresses.

    Args:
        allowlist: Origins that may resolve to a private address. Empty means
            the client may only reach public addresses, which is what a URL a
            user or a plugin supplied has to be held to.
    """

    def validate(request: httpx2.Request) -> None:
        validate_url_for_http_request(str(request.url), allowlist=allowlist)

    client = httpx2.Client(
        trust_env=has_proxy_env(),
        event_hooks={"request": [validate]},
    )
    # The sync backend is public-only by construction: the allowlist lives in the
    # fast-fail hook above, which is what a private-origin caller needs.
    install_sync_ssrf_protection(client)
    return client


_fallback_sync_client: httpx2.Client | None = None


def sync_httpx_client() -> httpx2.Client:
    """The app's shared public-only client.

    Handlers are synchronous, so they cannot await the client set up for the
    request, and opening one per call spends every connection it makes. This
    returns the single client created at startup, with its pool shared by every
    caller.

    A test or a command-line run has no app to borrow one from, so the first
    call creates it and later calls reuse it. Callers must not close it.
    """
    global _fallback_sync_client
    try:
        return ctx_httpx_sync_client.get()
    except LookupError:
        if _fallback_sync_client is None or _fallback_sync_client.is_closed:
            _fallback_sync_client = create_httpx_client(allowlist=frozenset())
        return _fallback_sync_client


@asynccontextmanager
async def set_context_var(var: ContextVar[_T], value: _T) -> AsyncGenerator[Token[_T]]:
    """Temporarily set a context variables."""
    token = var.set(value)
    yield token
    var.reset(token)


@asynccontextmanager
async def initialize_context() -> AsyncGenerator[None]:
    """Initialize context variables."""
    with create_httpx_client(allowlist=frozenset()) as sync_client:
        async with (
            create_aiohttp_session() as aiohttp_session,
            create_httpx_async_client() as httpx_client,
            set_context_var(ctx_aiohttp_session, aiohttp_session),
            set_context_var(ctx_httpx_client, httpx_client),
            set_context_var(ctx_httpx_sync_client, sync_client),
        ):
            yield


async def set_context_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Initialize context variables in FastAPI request-response cycle.

    This middleware is needed because the context initialized during the lifespan
    process is not available in the request-response cycle.
    """
    async with (
        set_context_var(ctx_aiohttp_session, request.app.state.aiohttp_session),
        set_context_var(ctx_httpx_client, request.app.state.httpx_client),
        set_context_var(ctx_httpx_sync_client, request.app.state.httpx_sync_client),
    ):
        return await call_next(request)
