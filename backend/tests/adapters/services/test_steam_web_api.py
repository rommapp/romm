import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from tests.factories import STEAM_ID

from adapters.services.steam import (
    SteamWebAPIError,
    SteamWebApiService,
    web_api_key_middleware,
)


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
    with patch("adapters.services.steam.ctx_aiohttp_session") as mock_ctx:
        mock_ctx.get.return_value = mock_session
        yield mock_session


def _service() -> SteamWebApiService:
    return SteamWebApiService()


async def test_sends_the_parameters_with_the_key_middleware(session):
    session.get.return_value = _response(
        {"response": {"success": 1, "steamid": STEAM_ID}}
    )

    await _service().resolve_vanity_url("gabe")

    await_args = session.get.await_args
    url = await_args.args[0]
    assert url.path == "/ISteamUser/ResolveVanityURL/v1/"
    assert url.query["vanityurl"] == "gabe"
    assert "key" not in url.query
    assert await_args.kwargs["middlewares"] == (web_api_key_middleware,)


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


async def test_an_unreachable_steam_is_an_error(session):
    session.get.side_effect = aiohttp.ClientConnectionError

    with pytest.raises(SteamWebAPIError, match="connect to Steam"):
        await _service().get_owned_games(STEAM_ID)


async def test_a_reply_that_is_not_json_is_an_error(session):
    response = _response({})
    response.read = AsyncMock(return_value=b"<html>busy</html>")
    session.get.return_value = response

    with pytest.raises(SteamWebAPIError, match="could not be read"):
        await _service().get_owned_games(STEAM_ID)


async def test_reads_a_players_achievements(session):
    unlocks = [{"apiname": "WIN", "achieved": 1, "unlocktime": 1_700_000_000}]
    session.get.return_value = _response(
        {"playerstats": {"steamID": STEAM_ID, "success": True, "achievements": unlocks}}
    )

    assert await _service().get_player_achievements(STEAM_ID, 220) == unlocks
    url = session.get.await_args.args[0]
    assert (url.query["steamid"], url.query["appid"]) == (STEAM_ID, "220")


async def test_a_game_without_stats_has_no_player_achievements(session):
    response = _response({"playerstats": {"success": False}})
    response.raise_for_status.side_effect = _error(400)
    session.get.return_value = response

    assert await _service().get_player_achievements(STEAM_ID, 220) == []


async def test_private_game_details_have_no_player_achievements(session):
    response = _response({"playerstats": {"success": False}})
    response.raise_for_status.side_effect = _error(403)
    session.get.return_value = response

    assert await _service().get_player_achievements(STEAM_ID, 220) is None


async def test_other_player_achievement_failures_are_an_error_with_their_status(
    session,
):
    response = _response({})
    response.raise_for_status.side_effect = _error(500)
    session.get.return_value = response

    with pytest.raises(SteamWebAPIError) as exc_info:
        await _service().get_player_achievements(STEAM_ID, 220)

    assert exc_info.value.status == 500


@pytest.mark.parametrize(
    "playerstats", [["not", "an", "object"], {"success": True, "achievements": "ACH"}]
)
async def test_a_malformed_player_achievements_reply_has_none(
    session, lenient, playerstats
):
    session.get.return_value = _response({"playerstats": playerstats})

    assert await _service().get_player_achievements(STEAM_ID, 220) == []
