"""A local HTTP server that plays back scripted replies, for the API client tests."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestServer

from utils.context import ctx_aiohttp_session

# A float is a delay that outlasts the client's timeout; bytes go out as-is.
Reply = tuple[int, Any] | float


class ScriptedServer:
    """Answers each request with the next reply scripted for its endpoint."""

    def __init__(self) -> None:
        self.replies: dict[str, list[Reply]] = {}
        self.requests: list[web.Request] = []

    def endpoint(self, name: str) -> list[web.Request]:
        return [r for r in self.requests if r.match_info["endpoint"] == name]

    async def handle(self, request: web.Request) -> web.StreamResponse:
        self.requests.append(request)
        reply = self.replies[request.match_info["endpoint"]].pop(0)
        if isinstance(reply, float):
            await asyncio.sleep(reply)
            return web.json_response({})
        status, body = reply
        if isinstance(body, bytes):
            return web.Response(status=status, body=body)
        return web.json_response(body, status=status)


@asynccontextmanager
async def scripted_server(prefix: str) -> AsyncIterator[tuple[ScriptedServer, str]]:
    """Serve `{prefix}/{endpoint}` and route the client session to it.

    Yields the server and the base URL to hand the client.
    """
    fake = ScriptedServer()
    app = web.Application()
    app.router.add_route("*", f"{prefix}/{{endpoint}}", fake.handle)
    server = TestServer(app)
    await server.start_server()
    session = aiohttp.ClientSession()
    token = ctx_aiohttp_session.set(session)
    try:
        yield fake, str(server.make_url(prefix))
    finally:
        ctx_aiohttp_session.reset(token)
        await session.close()
        await server.close()
