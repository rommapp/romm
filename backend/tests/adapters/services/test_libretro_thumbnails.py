"""Tests for the libretro thumbnails service."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp.client_exceptions
import pytest

from adapters.services.libretro_thumbnails import (
    LIBRETRO_LISTING_CACHE_TTL,
    LIBRETRO_MISSING_LISTING_CACHE_TTL,
    LibretroThumbnailsService,
)
from adapters.services.libretro_thumbnails_types import LibretroArtType
from handler.redis_handler import async_cache

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
    assert json.loads(await async_cache.get(cache_key)) == result
    assert await async_cache.ttl(cache_key) == LIBRETRO_LISTING_CACHE_TTL


@pytest.mark.asyncio
async def test_fetch_listing_caches_miss_on_404(service):
    """A missing directory is stable, so the empty result should be cached."""
    system_name = "Test - Missing"
    session = mock_session_raising(response_error(404))

    assert await fetch_with(service, session, system_name) == []

    cache_key = service._cache_key(system_name, LibretroArtType.LOGO)
    assert json.loads(await async_cache.get(cache_key)) == []
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
    assert json.loads(await async_cache.get(cache_key)) == []


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
