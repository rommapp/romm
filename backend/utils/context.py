from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar, Token
from typing import TypeVar

import httpx
from fastapi import Request, Response

_T = TypeVar("_T")

ctx_httpx_client: ContextVar[httpx.AsyncClient] = ContextVar("httpx_client")


@asynccontextmanager
async def set_context_var(
    var: ContextVar[_T], value: _T
) -> AsyncGenerator[Token[_T], None]:
    """Temporarily set a context variables."""
    token = var.set(value)
    yield token
    var.reset(token)


@asynccontextmanager
async def initialize_context() -> AsyncGenerator[None, None]:
    """Initialize context variables."""
    async with httpx.AsyncClient() as httpx_client:
        async with set_context_var(ctx_httpx_client, httpx_client):
            yield


async def set_context_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Initialize context variables in FastAPI request-response cycle.

    This middleware is needed because the context initialized during the lifespan
    process is not available in the request-response cycle.
    """
    async with set_context_var(ctx_httpx_client, request.app.state.httpx_client):
        return await call_next(request)
