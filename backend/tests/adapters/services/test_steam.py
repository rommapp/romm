import http
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from fastapi import HTTPException, status

from adapters.services.steam import STEAM_LIBRARY_CAPSULE_URL, SteamService


def _response(json_body: object) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=json_body)
    return response


def _error(status_code: int) -> aiohttp.ClientResponseError:
    return aiohttp.ClientResponseError(
        request_info=MagicMock(), history=(), status=status_code
    )


@pytest.fixture(autouse=True)
def no_backoff_sleep():
    with patch("adapters.services.steam.asyncio.sleep", new_callable=AsyncMock):
        yield


@pytest.fixture
def session():
    mock_session = AsyncMock()
    with patch("adapters.services.steam.ctx_aiohttp_session") as mock_ctx:
        mock_ctx.get.return_value = mock_session
        yield mock_session


async def test_search_apps_returns_items(session):
    session.get.return_value = _response(
        {"total": 1, "items": [{"type": "app", "name": "Portal", "id": 400}]}
    )

    items = await SteamService().search_apps("portal")

    assert items == [{"type": "app", "name": "Portal", "id": 400}]
    assert "storesearch" in str(session.get.await_args.args[0])


async def test_search_apps_handles_empty_payload(session):
    session.get.return_value = _response({})

    assert await SteamService().search_apps("nothing at all") == []


async def test_get_app_details_unwraps_envelope(session):
    session.get.return_value = _response(
        {"400": {"success": True, "data": {"type": "game", "name": "Portal"}}}
    )

    details = await SteamService().get_app_details(400)

    assert details == {"type": "game", "name": "Portal"}


async def test_get_app_details_returns_none_on_unsuccessful_envelope(session):
    """Steam reports an unknown or region-locked app as success: false."""
    session.get.return_value = _response({"400": {"success": False}})

    assert await SteamService().get_app_details(400) is None


async def test_request_retries_once_after_rate_limit(session):
    session.get.side_effect = [
        _error(http.HTTPStatus.TOO_MANY_REQUESTS),
        _response({"total": 0, "items": []}),
    ]

    assert await SteamService().search_apps("portal") == []
    assert session.get.await_count == 2


async def test_request_gives_up_after_repeated_rate_limits(session):
    session.get.side_effect = _error(http.HTTPStatus.TOO_MANY_REQUESTS)

    assert await SteamService().search_apps("portal") == []
    assert session.get.await_count == 3


async def test_request_swallows_other_status_errors(session):
    """A storefront hiccup must not abort the surrounding scan."""
    session.get.side_effect = _error(http.HTTPStatus.INTERNAL_SERVER_ERROR)

    assert await SteamService().get_app_details(400) is None
    assert session.get.await_count == 1


async def test_request_degrades_when_the_body_is_not_a_mapping(session):
    """A throttled storefront answers 200 with a bare `null`."""
    session.get.return_value = _response(None)

    assert await SteamService().get_app_details(400) is None
    assert await SteamService().search_apps("portal") == []


async def test_request_raises_on_connection_error(session):
    session.get.side_effect = aiohttp.ClientConnectionError()

    with pytest.raises(HTTPException) as exc_info:
        await SteamService().search_apps("portal")

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


async def test_get_app_details_passes_filters(session):
    session.get.return_value = _response({"220": {"success": True, "data": {}}})

    await SteamService().get_app_details(220, filters="basic")

    await_args = session.get.await_args
    assert await_args is not None
    assert "filters=basic" in str(await_args.args[0])


async def test_library_capsule_url_when_the_cdn_serves_one(session):
    session.head.return_value = MagicMock(status=http.HTTPStatus.OK)

    url = await SteamService().get_library_capsule_url(400)

    assert url == STEAM_LIBRARY_CAPSULE_URL.format(app_id=400)


async def test_library_capsule_url_is_none_when_missing(session):
    session.head.return_value = MagicMock(status=http.HTTPStatus.NOT_FOUND)

    assert await SteamService().get_library_capsule_url(400) is None


async def test_library_capsule_url_is_none_when_the_probe_fails(session):
    """A CDN hiccup must fall through to the caller's header-image fallback."""
    session.head.side_effect = aiohttp.ClientConnectionError()

    assert await SteamService().get_library_capsule_url(400) is None
