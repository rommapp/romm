import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from adapters.services.steam_web_api import SteamWebAPIError, SteamWebAPIService

STEAM_ID = "76561197960287930"


def _response(json_body: object) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.read = AsyncMock(return_value=json.dumps(json_body).encode())
    return response


def _error(status_code: int) -> aiohttp.ClientResponseError:
    return aiohttp.ClientResponseError(
        request_info=MagicMock(), history=(), status=status_code
    )


@pytest.fixture(autouse=True)
def no_backoff_sleep():
    with patch("adapters.services.provider_http.asyncio.sleep", new_callable=AsyncMock):
        yield


@pytest.fixture
def session():
    mock_session = AsyncMock()
    with patch("adapters.services.steam_web_api.ctx_aiohttp_session") as mock_ctx:
        mock_ctx.get.return_value = mock_session
        yield mock_session


def _service() -> SteamWebAPIService:
    return SteamWebAPIService("secret-key")


async def test_sends_the_key_and_parameters(session):
    session.get.return_value = _response(
        {"response": {"success": 1, "steamid": STEAM_ID}}
    )

    await _service().resolve_vanity_url("gabe")

    url = session.get.await_args.args[0]
    assert url.path == "/ISteamUser/ResolveVanityURL/v1/"
    assert url.query["key"] == "secret-key"
    assert url.query["vanityurl"] == "gabe"


async def test_resolves_a_custom_name(session):
    session.get.return_value = _response(
        {"response": {"success": 1, "steamid": STEAM_ID}}
    )

    assert await _service().resolve_vanity_url("gabe") == STEAM_ID


async def test_an_unused_custom_name_resolves_to_nothing(session):
    session.get.return_value = _response(
        {"response": {"success": 42, "message": "No match"}}
    )

    assert await _service().resolve_vanity_url("nobody") is None


async def test_returns_the_player_summary(session):
    player = {
        "steamid": STEAM_ID,
        "personaname": "Gabe",
        "profileurl": "https://steamcommunity.com/id/gabe/",
        "communityvisibilitystate": 3,
    }
    session.get.return_value = _response({"response": {"players": [player]}})

    assert await _service().get_player_summary(STEAM_ID) == player


async def test_an_unknown_account_has_no_summary(session):
    session.get.return_value = _response({"response": {"players": []}})

    assert await _service().get_player_summary(STEAM_ID) is None


async def test_lists_owned_games(session):
    games = [{"appid": 220, "name": "Half-Life 2", "playtime_forever": 90}]
    session.get.return_value = _response(
        {"response": {"game_count": 1, "games": games}}
    )

    assert await _service().get_owned_games(STEAM_ID) == games
    url = session.get.await_args.args[0]
    assert url.query["include_appinfo"] == "1"
    assert url.query["include_played_free_games"] == "1"


async def test_an_account_owning_nothing_lists_no_games(session):
    session.get.return_value = _response({"response": {"game_count": 0}})

    assert await _service().get_owned_games(STEAM_ID) == []


async def test_a_private_library_lists_nothing_at_all(session):
    session.get.return_value = _response({"response": {}})

    assert await _service().get_owned_games(STEAM_ID) is None


@pytest.mark.parametrize("status_code", [401, 403])
async def test_a_rejected_key_is_an_error(session, status_code: int):
    response = _response({})
    response.raise_for_status.side_effect = _error(status_code)
    session.get.return_value = response

    with pytest.raises(SteamWebAPIError, match="API key"):
        await _service().get_owned_games(STEAM_ID)


async def test_a_timeout_on_every_attempt_is_an_error(session):
    session.get.side_effect = TimeoutError

    with pytest.raises(SteamWebAPIError, match="in time"):
        await _service().get_owned_games(STEAM_ID)
