from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar, Token
from typing import TypeVar

import aiohttp
import httpx
from fastapi import Request, Response

from config import has_proxy_env
from utils.ssrf import (
    install_async_ssrf_protection,
    install_sync_ssrf_protection,
    validate_url_for_http_request,
)

_T = TypeVar("_T")

ctx_aiohttp_session: ContextVar[aiohttp.ClientSession] = ContextVar("aiohttp_session")
ctx_httpx_client: ContextVar[httpx.AsyncClient] = ContextVar("httpx_client")


def _validate_request_url_sync(request: httpx.Request) -> None:
    validate_url_for_http_request(str(request.url))


async def _validate_request_url_async(request: httpx.Request) -> None:
    validate_url_for_http_request(str(request.url))


def create_aiohttp_session() -> aiohttp.ClientSession:
    return aiohttp.ClientSession(trust_env=has_proxy_env())


def create_httpx_async_client() -> httpx.AsyncClient:
    client = httpx.AsyncClient(
        trust_env=has_proxy_env(),
        event_hooks={"request": [_validate_request_url_async]},
    )
    install_async_ssrf_protection(client)
    return client


def create_httpx_client() -> httpx.Client:
    client = httpx.Client(
        trust_env=has_proxy_env(),
        event_hooks={"request": [_validate_request_url_sync]},
    )
    install_sync_ssrf_protection(client)
    return client


@asynccontextmanager
async def set_context_var(var: ContextVar[_T], value: _T) -> AsyncGenerator[Token[_T]]:
    """Temporarily set a context variables."""
    token = var.set(value)
    yield token
    var.reset(token)


@asynccontextmanager
async def initialize_context() -> AsyncGenerator[None]:
    """Initialize context variables."""
    async with (
        create_aiohttp_session() as aiohttp_session,
        create_httpx_async_client() as httpx_client,
        set_context_var(ctx_aiohttp_session, aiohttp_session),
        set_context_var(ctx_httpx_client, httpx_client),
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
    ):
        return await call_next(request)
