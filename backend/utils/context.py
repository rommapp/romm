from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar, Token
from typing import TypeVar

import aiohttp
import httpx
from fastapi import Request, Response

_T = TypeVar("_T")

ctx_aiohttp_session: ContextVar[aiohttp.ClientSession] = ContextVar("aiohttp_session")
ctx_httpx_client: ContextVar[httpx.AsyncClient] = ContextVar("httpx_client")


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
        aiohttp.ClientSession() as aiohttp_session,
        httpx.AsyncClient() as httpx_client,
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
