"""Tests for the libretro thumbnails service."""

import asyncio
import json
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import aiohttp.client_exceptions
import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestServer

from adapters.services import libretro_thumbnails
from adapters.services.libretro_thumbnails import (
    LIBRETRO_LISTING_CACHE_TTL,
    LIBRETRO_MISSING_LISTING_CACHE_TTL,
    LibretroThumbnailsService,
)
from adapters.services.libretro_thumbnails_types import LibretroArtType
from handler.redis_handler import async_cache
from utils.context import ctx_aiohttp_session

LISTING_BODY = """
<html><body>
<a href="?C=N;O=D">Name</a>
<a href="/">Parent Directory</a>
<a href="Final%20Fantasy%20VII%20(USA).png">Final Fantasy VII (USA).png</a>
</body></html>
"""


@pytest.fixture
def service() -> LibretroThumbnailsService:
    return LibretroThumbnailsService()


def mock_session_returning(body: str) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.text = AsyncMock(return_value=body)
    session = MagicMock()
    session.get = AsyncMock(return_value=response)
    return session


def mock_session_raising(exc: Exception) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.side_effect = exc
    session = MagicMock()
    session.get = AsyncMock(return_value=response)
    return session


def response_error(status: int) -> aiohttp.client_exceptions.ClientResponseError:
    return aiohttp.client_exceptions.ClientResponseError(
        request_info=MagicMock(), history=(), status=status
    )


async def fetch_with(
    service: LibretroThumbnailsService,
    session: MagicMock,
    system_name: str,
    art_type: LibretroArtType = LibretroArtType.LOGO,
) -> list[str]:
    mock_context = MagicMock()
    mock_context.get.return_value = session
    with patch(
        "adapters.services.libretro_thumbnails.ctx_aiohttp_session", mock_context
    ):
        return await service.fetch_listing(system_name, art_type)


@pytest.mark.asyncio
async def test_fetch_listing_caches_parsed_filenames(service):
    system_name = "Test - Success"
    session = mock_session_returning(LISTING_BODY)

    result = await fetch_with(service, session, system_name)

    assert result == ["Final Fantasy VII (USA).png"]

    cache_key = service._cache_key(system_name, LibretroArtType.LOGO)
    cached = await async_cache.get(cache_key)
    assert cached is not None
    assert json.loads(cached) == result
    assert await async_cache.ttl(cache_key) == LIBRETRO_LISTING_CACHE_TTL


@pytest.mark.asyncio
async def test_fetch_listing_caches_miss_on_404(service):
    """A missing directory is stable, so the empty result should be cached."""
    system_name = "Test - Missing"
    session = mock_session_raising(response_error(404))

    assert await fetch_with(service, session, system_name) == []

    cache_key = service._cache_key(system_name, LibretroArtType.LOGO)
    cached = await async_cache.get(cache_key)
    assert cached is not None
    assert json.loads(cached) == []
    assert await async_cache.ttl(cache_key) == LIBRETRO_MISSING_LISTING_CACHE_TTL


@pytest.mark.asyncio
async def test_fetch_listing_serves_cached_miss_without_a_request(service):
    """The second lookup for a missing directory must not hit the network."""
    system_name = "Test - Missing Repeat"
    first_session = mock_session_raising(response_error(404))
    await fetch_with(service, first_session, system_name)

    second_session = mock_session_raising(response_error(404))
    assert await fetch_with(service, second_session, system_name) == []

    second_session.get.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_listing_caches_miss_on_410(service):
    system_name = "Test - Gone"
    session = mock_session_raising(response_error(410))

    assert await fetch_with(service, session, system_name) == []

    cache_key = service._cache_key(system_name, LibretroArtType.LOGO)
    cached = await async_cache.get(cache_key)
    assert cached is not None
    assert json.loads(cached) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [403, 408, 429, 503])
async def test_fetch_listing_does_not_cache_retryable_errors(service, status):
    """A directory that exists must not be masked by a transient failure."""
    system_name = f"Test - Retryable {status}"
    session = mock_session_raising(response_error(status))

    assert await fetch_with(service, session, system_name) == []

    cache_key = service._cache_key(system_name, LibretroArtType.LOGO)
    assert await async_cache.get(cache_key) is None


@pytest.mark.asyncio
async def test_fetch_listing_does_not_cache_connection_errors(service):
    system_name = "Test - Connection Error"
    session = mock_session_raising(
        aiohttp.client_exceptions.ClientConnectionError("nope")
    )

    assert await fetch_with(service, session, system_name) == []

    cache_key = service._cache_key(system_name, LibretroArtType.LOGO)
    assert await async_cache.get(cache_key) is None


class LibretroServer:
    """Answers every path with the next scripted reply; a float is a delay."""

    def __init__(self) -> None:
        self.replies: list[tuple[int, str] | float] = []
        self.requests: list[web.Request] = []

    async def handle(self, request: web.Request) -> web.StreamResponse:
        self.requests.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, float):
            await asyncio.sleep(reply)
            return web.Response(text="")
        status, body = reply
        return web.Response(status=status, text=body, content_type="text/html")


@pytest_asyncio.fixture
async def libretro_server(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[LibretroServer, LibretroThumbnailsService]]:
    monkeypatch.setattr(libretro_thumbnails, "LIBRETRO_LISTING_TIMEOUT", 0.2)
    monkeypatch.setattr(libretro_thumbnails, "LIBRETRO_HEAD_TIMEOUT", 0.2)
    fake = LibretroServer()
    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", fake.handle)
    server = TestServer(app)
    await server.start_server()
    session = aiohttp.ClientSession()
    token = ctx_aiohttp_session.set(session)
    try:
        yield fake, LibretroThumbnailsService(base_url=str(server.make_url("")))
    finally:
        ctx_aiohttp_session.reset(token)
        await session.close()
        await server.close()


class TestAgainstAServer:
    async def test_reads_the_listing_and_asks_for_it_once(
        self, libretro_server: tuple[LibretroServer, LibretroThumbnailsService]
    ):
        fake, service = libretro_server
        fake.replies = [
            (
                200,
                LISTING_BODY
                + '<a name="top">Top</a><a href="readme.txt">readme.txt</a>'
                + '<a href="../x.png">x</a>'
                + '<a class="icon" href="Chrono%20Trigger%20(USA).png">CT</a>',
            )
        ]

        first = await service.fetch_listing("Test - Server", LibretroArtType.BOX_ART)
        second = await service.fetch_listing("Test - Server", LibretroArtType.BOX_ART)

        assert (
            first
            == second
            == ["Final Fantasy VII (USA).png", "Chrono Trigger (USA).png"]
        )
        [request] = fake.requests
        assert request.path == "/Test - Server/Named_Boxarts/"
        assert request.query["F"] == "2"
        assert request.headers["User-Agent"].startswith("RomM/")

    async def test_a_corrupt_cached_listing_is_fetched_again(
        self, libretro_server: tuple[LibretroServer, LibretroThumbnailsService]
    ):
        fake, service = libretro_server
        key = service._cache_key("Test - Corrupt", LibretroArtType.BOX_ART)
        await async_cache.set(key, "{not json")
        fake.replies = [(200, LISTING_BODY)]

        assert await service.fetch_listing(
            "Test - Corrupt", LibretroArtType.BOX_ART
        ) == ["Final Fantasy VII (USA).png"]

    async def test_a_timed_out_listing_is_empty_and_not_cached(
        self, libretro_server: tuple[LibretroServer, LibretroThumbnailsService]
    ):
        fake, service = libretro_server
        fake.replies = [5.0]

        assert await service.fetch_listing("Test - Slow", LibretroArtType.BOX_ART) == []

        key = service._cache_key("Test - Slow", LibretroArtType.BOX_ART)
        assert await async_cache.get(key) is None

    @pytest.mark.parametrize(
        ("reply", "reachable"),
        [((200, ""), True), ((404, ""), True), ((503, ""), False), (5.0, False)],
        ids=["ok", "not_found", "down", "timeout"],
    )
    async def test_head_reports_whether_the_server_answers(
        self,
        libretro_server: tuple[LibretroServer, LibretroThumbnailsService],
        reply: tuple[int, str] | float,
        reachable: bool,
    ):
        fake, service = libretro_server
        fake.replies = [reply]

        assert await service.head() is reachable
