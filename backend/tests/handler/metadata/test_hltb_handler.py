import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException, status

from handler.metadata.hltb_handler import HLTBHandler
from utils import get_version
from utils.hltb_search import HLTB_BASE_URL, SESSION_MINT_SUFFIX

SEARCH_URL = f"{HLTB_BASE_URL}/api/search/site"


def _handler_without_session() -> HLTBHandler:
    """A handler pointed at an endpoint, before any session has been minted."""
    handler = HLTBHandler()
    handler.search_url = SEARCH_URL
    handler.search_init_url = f"{SEARCH_URL}{SESSION_MINT_SUFFIX}"
    return handler


def _handler() -> HLTBHandler:
    handler = _handler_without_session()
    handler.security_token = "token-1"
    handler.hp_key = "ign_aaaa"
    handler.hp_val = "val-1"
    return handler


def _response(status_code: int = 200, json_body: dict | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=response
        )
    else:
        response.json.return_value = json_body or {}
    return response


@pytest.fixture(autouse=True)
def acquire():
    with (
        patch(
            "handler.metadata.hltb_handler._rate_limiter.acquire",
            new_callable=AsyncMock,
        ) as mock_acquire,
        patch("handler.metadata.hltb_handler.asyncio.sleep", new_callable=AsyncMock),
    ):
        yield mock_acquire


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_request_renews_session_and_retries_on_403(mock_ctx_httpx_client):
    handler = _handler()
    mock_client = AsyncMock()
    mock_client.post.side_effect = [
        _response(status.HTTP_403_FORBIDDEN),
        _response(json_body={"data": [{"game_id": 1}]}),
    ]
    # The renewal goes through /init and hands back a fresh session.
    mock_client.get.return_value = _response(
        json_body={"token": "token-2", "hpKey": "ign_bbbb", "hpVal": "val-2"}
    )
    mock_ctx_httpx_client.get.return_value = mock_client

    result = await handler._request(handler.search_url, {"a": 1})

    assert result == {"data": [{"game_id": 1}]}
    assert mock_client.post.await_count == 2
    mock_client.get.assert_awaited_once()

    # The retry must carry the renewed session, not the rejected one.
    retry_kwargs = mock_client.post.await_args_list[1].kwargs
    assert retry_kwargs["headers"]["x-auth-token"] == "token-2"
    assert retry_kwargs["headers"]["x-hp-key"] == "ign_bbbb"
    assert retry_kwargs["headers"]["x-hp-val"] == "val-2"
    # The rotated honeypot key replaces the old one rather than joining it.
    assert retry_kwargs["json"] == {"a": 1, "ign_bbbb": "val-2"}


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_request_does_not_mutate_caller_payload(mock_ctx_httpx_client):
    handler = _handler()
    mock_client = AsyncMock()
    mock_client.post.return_value = _response(json_body={"data": []})
    mock_ctx_httpx_client.get.return_value = mock_client

    payload = {"a": 1}
    await handler._request(handler.search_url, payload)

    assert payload == {"a": 1}


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_request_uses_session_renewed_while_it_was_paced(
    mock_ctx_httpx_client, acquire
):
    # The handler is a shared singleton, so a peer scanning another ROM can renew
    # the session while this call is waiting on the rate limiter.
    handler = _handler()
    mock_client = AsyncMock()
    mock_client.post.return_value = _response(json_body={"data": []})
    mock_ctx_httpx_client.get.return_value = mock_client

    async def renew_while_waiting() -> None:
        handler.security_token = "token-from-peer"
        handler.hp_key = "ign_peer"
        handler.hp_val = "val-peer"

    acquire.side_effect = renew_while_waiting

    await handler._request(handler.search_url, {"a": 1})

    kwargs = mock_client.post.await_args.kwargs
    assert kwargs["headers"]["x-auth-token"] == "token-from-peer"
    assert kwargs["json"] == {"a": 1, "ign_peer": "val-peer"}


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_request_bails_if_session_is_lost_while_it_was_paced(
    mock_ctx_httpx_client, acquire
):
    handler = _handler()
    mock_client = AsyncMock()
    mock_ctx_httpx_client.get.return_value = mock_client

    async def lose_session_while_waiting() -> None:
        handler.security_token = None

    acquire.side_effect = lose_session_while_waiting

    assert await handler._request(handler.search_url, {}) == {}
    mock_client.post.assert_not_awaited()


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_session_renewal_is_rate_limited_too(mock_ctx_httpx_client, acquire):
    handler = _handler()
    mock_client = AsyncMock()
    mock_client.post.side_effect = [
        _response(status.HTTP_403_FORBIDDEN),
        _response(json_body={"data": []}),
    ]
    mock_client.get.return_value = _response(
        json_body={"token": "token-2", "hpKey": "ign_bbbb", "hpVal": "val-2"}
    )
    mock_ctx_httpx_client.get.return_value = mock_client

    await handler._request(handler.search_url, {})

    # Two POSTs plus the /init renewal in between, all paced.
    assert acquire.await_count == 3


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_github_endpoint_fetch_is_not_rate_limited(
    mock_ctx_httpx_client, acquire
):
    # The endpoint fixture lives on GitHub, so it should not spend HLTB budget.
    handler = HLTBHandler()
    mock_client = AsyncMock()
    mock_client.get.return_value = _response_with_text(
        "https://howlongtobeat.com/api/rotated"
    )
    mock_ctx_httpx_client.get.return_value = mock_client

    await handler._fetch_search_endpoint()

    acquire.assert_not_awaited()


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_debug_log_does_not_leak_session_material(mock_ctx_httpx_client):
    # Logs are downloadable via /api/logs and routinely pasted into bug reports,
    # and the token decodes to a string containing the host's public IP.
    handler = _handler()
    mock_client = AsyncMock()
    mock_client.post.return_value = _response(json_body={"data": []})
    mock_ctx_httpx_client.get.return_value = mock_client

    with patch("handler.metadata.hltb_handler.log.debug") as mock_debug:
        await handler._request(handler.search_url, {"searchTerms": ["Chrono"]})

    logged = repr(mock_debug.call_args.args)
    for secret in ("token-1", "ign_aaaa", "val-1"):
        assert secret not in logged

    # The parts that make the log useful are still there.
    assert "Chrono" in logged
    assert "[redacted]" in logged


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_request_backs_off_and_retries_on_429(mock_ctx_httpx_client):
    handler = _handler()
    mock_client = AsyncMock()
    mock_client.post.side_effect = [
        _response(status.HTTP_429_TOO_MANY_REQUESTS),
        _response(json_body={"data": []}),
    ]
    mock_ctx_httpx_client.get.return_value = mock_client

    assert await handler._request(handler.search_url, {}) == {"data": []}
    assert mock_client.post.await_count == 2
    # A rate limit is not a session problem, so no renewal should be attempted.
    mock_client.get.assert_not_awaited()


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_request_gives_up_when_session_renewal_fails(mock_ctx_httpx_client):
    handler = _handler()
    mock_client = AsyncMock()
    mock_client.post.return_value = _response(status.HTTP_403_FORBIDDEN)
    mock_client.get.return_value = _response(json_body={})
    mock_ctx_httpx_client.get.return_value = mock_client

    assert await handler._request(handler.search_url, {}) == {}
    assert mock_client.post.await_count == 1


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_persistent_403_reports_session_cause_not_connectivity(
    mock_ctx_httpx_client,
):
    handler = _handler()
    mock_client = AsyncMock()
    mock_client.post.return_value = _response(status.HTTP_403_FORBIDDEN)
    mock_client.get.return_value = _response(
        json_body={"token": "token-2", "hpKey": "ign_bbbb", "hpVal": "val-2"}
    )
    mock_ctx_httpx_client.get.return_value = mock_client

    with pytest.raises(HTTPException) as exc_info:
        await handler._request(handler.search_url, {})

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "internet connection" not in exc_info.value.detail
    assert "rejected the session" in exc_info.value.detail
    assert mock_client.post.await_count == 3


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_rotated_endpoint_reports_404_cause(mock_ctx_httpx_client):
    handler = _handler()
    mock_client = AsyncMock()
    mock_client.post.return_value = _response(status.HTTP_404_NOT_FOUND)
    mock_ctx_httpx_client.get.return_value = mock_client

    with pytest.raises(HTTPException) as exc_info:
        await handler._request("https://howlongtobeat.com/api/find", {})

    assert "rotated" in exc_info.value.detail
    # A 404 is not retryable, so it should fail on the first attempt.
    assert mock_client.post.await_count == 1


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_connect_error_still_reports_connectivity(mock_ctx_httpx_client):
    handler = _handler()
    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.ConnectError("no route")
    mock_ctx_httpx_client.get.return_value = mock_client

    with pytest.raises(HTTPException) as exc_info:
        await handler._request(handler.search_url, {})

    assert "internet connection" in exc_info.value.detail


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_request_returns_empty_without_a_session(mock_ctx_httpx_client):
    handler = _handler_without_session()
    mock_client = AsyncMock()
    mock_client.get.return_value = _response(json_body={})
    mock_ctx_httpx_client.get.return_value = mock_client

    assert await handler._request(handler.search_url, {}) == {}
    mock_client.post.assert_not_awaited()


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_request_mints_a_session_a_failed_startup_never_got(
    mock_ctx_httpx_client,
):
    handler = _handler_without_session()
    mock_client = AsyncMock()
    mock_client.get.return_value = _response(
        json_body={"token": "token-late", "hpKey": "ign_late", "hpVal": "val-late"}
    )
    mock_client.post.return_value = _response(json_body={"data": []})
    mock_ctx_httpx_client.get.return_value = mock_client

    assert await handler._request(handler.search_url, {"a": 1}) == {"data": []}

    # The mint has to address the endpoint being searched, not a stale default.
    assert mock_client.get.await_args.args[0] == handler.search_init_url
    kwargs = mock_client.post.await_args.kwargs
    assert kwargs["headers"]["x-auth-token"] == "token-late"
    assert kwargs["json"] == {"a": 1, "ign_late": "val-late"}


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_a_failed_mint_is_not_retried_by_every_lookup(mock_ctx_httpx_client):
    handler = _handler_without_session()
    mock_client = AsyncMock()
    mock_client.get.return_value = _response(json_body={})
    mock_ctx_httpx_client.get.return_value = mock_client

    for _ in range(5):
        assert await handler._request(handler.search_url, {}) == {}

    # HLTB being down must not cost every ROM in a scan its own round trip.
    mock_client.get.assert_awaited_once()
    mock_client.post.assert_not_awaited()


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_concurrent_lookups_mint_one_shared_session(mock_ctx_httpx_client):
    handler = _handler_without_session()
    mock_client = AsyncMock()
    mint_reached = asyncio.Event()
    mint_may_finish = asyncio.Event()

    async def blocking_mint(*args, **kwargs) -> MagicMock:
        # Hold /init open so every other lookup reaches _ensure_session meanwhile.
        mint_reached.set()
        await mint_may_finish.wait()
        return _response(
            json_body={"token": "token-1", "hpKey": "ign_aaaa", "hpVal": "val-1"}
        )

    mock_client.get.side_effect = blocking_mint
    mock_client.post.return_value = _response(json_body={"data": []})
    mock_ctx_httpx_client.get.return_value = mock_client

    lookups = [
        asyncio.create_task(handler._request(handler.search_url, {})) for _ in range(5)
    ]
    await mint_reached.wait()
    mint_may_finish.set()
    await asyncio.gather(*lookups)

    # A scan starts many lookups at once, and HLTB must not see a mint from each.
    mock_client.get.assert_awaited_once()
    assert mock_client.post.await_count == 5


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_initialize_fetches_endpoint_then_session(mock_ctx_httpx_client):
    handler = HLTBHandler()
    mock_client = AsyncMock()
    mock_client.get.side_effect = [
        _response_with_text("https://howlongtobeat.com/api/rotated"),
        _response(json_body={"token": "t", "hpKey": "k", "hpVal": "v"}),
    ]
    mock_ctx_httpx_client.get.return_value = mock_client

    await handler.initialize()

    assert handler.search_url == "https://howlongtobeat.com/api/rotated"
    assert handler.search_init_url == "https://howlongtobeat.com/api/rotated/init"
    assert handler._has_session()
    # The session must be requested from the rotated endpoint, not the stale default.
    assert (
        mock_client.get.await_args_list[1].args[0]
        == "https://howlongtobeat.com/api/rotated/init"
    )


def _response_with_text(text: str) -> MagicMock:
    response = _response()
    response.text = text
    return response


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_heartbeat_sends_the_user_agent_hltb_requires(mock_ctx_httpx_client):
    handler = HLTBHandler()
    mock_client = AsyncMock()
    mock_client.get.return_value = _response()
    mock_ctx_httpx_client.get.return_value = mock_client

    with patch.object(handler, "is_enabled", return_value=True):
        assert await handler.heartbeat() is True

    # HLTB rejects requests without a recognised user agent.
    headers = mock_client.get.await_args.kwargs["headers"]
    assert headers["User-Agent"] == f"RomM/{get_version()}"
    assert headers["Referer"] == "https://howlongtobeat.com"


def _game(game_id: int, name: str, *, timed: bool = True) -> dict:
    """A search result carrying only the fields matching depends on."""
    time = 3600 if timed else 0
    return {
        "game_id": game_id,
        "game_name": name,
        "game_image": "",
        "comp_main": time,
        "comp_plus": time,
        "comp_100": time,
        "comp_all": time,
        "comp_main_count": 1,
        "comp_plus_count": 1,
        "comp_100_count": 1,
        "comp_all_count": 1,
        "release_world": 2008,
        "review_score": 70,
        "count_review": 5,
        "profile_popular": 3,
        "count_comp": 4,
    }


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
async def test_series_prefix_the_catalogue_omits_still_matches():
    """ "007: Quantum of Solace" scores 0.838 against "Quantum of Solace",
    under the gate, so the part after the separator has to be searched too."""
    handler = _handler()
    searched: list[str] = []

    async def search_games(term, _platform_slug):
        searched.append(term)
        return [_game(7467, "Quantum of Solace")]

    with patch.object(handler, "search_games", side_effect=search_games):
        rom = await handler.get_rom("007 - Quantum of Solace (USA).chd", "ps2")

    assert rom["hltb_id"] == 7467
    assert searched == ["007: quantum of solace", "quantum of solace"]


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
async def test_full_term_match_does_not_trigger_a_second_search():
    handler = _handler()
    searched: list[str] = []

    async def search_games(term, _platform_slug):
        searched.append(term)
        return [_game(4806, "James Bond 007: Agent Under Fire")]

    with patch.object(handler, "search_games", side_effect=search_games):
        rom = await handler.get_rom(
            "James Bond 007 - Agent Under Fire (USA).chd", "ps2"
        )

    assert rom["hltb_id"] == 4806
    assert len(searched) == 1


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
async def test_term_without_a_separator_is_not_searched_twice():
    handler = _handler()
    searched: list[str] = []

    async def search_games(term, _platform_slug):
        searched.append(term)
        return []

    with patch.object(handler, "search_games", side_effect=search_games):
        rom = await handler.get_rom("Nothing Like It (USA).chd", "ps2")

    assert rom["hltb_id"] is None
    assert searched == ["nothing like it"]


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
async def test_hyphen_inside_a_word_does_not_trigger_a_retry():
    """A retry on "man 2" would invite a match on an unrelated game."""
    handler = _handler()
    searched: list[str] = []

    async def search_games(term, _platform_slug):
        searched.append(term)
        return []

    with patch.object(handler, "search_games", side_effect=search_games):
        rom = await handler.get_rom("Spider-Man 2 (USA).chd", "ps2")

    assert rom["hltb_id"] is None
    assert searched == ["spider-man 2"]


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
async def test_retry_still_requires_recorded_times():
    """A catalogue entry nobody has submitted a time for is not a match."""
    handler = _handler()

    async def search_games(_term, _platform_slug):
        return [_game(7467, "Quantum of Solace", timed=False)]

    with patch.object(handler, "search_games", side_effect=search_games):
        rom = await handler.get_rom("007 - Quantum of Solace (USA).chd", "ps2")

    assert rom["hltb_id"] is None


def _game_page(game: dict | None) -> MagicMock:
    """A game page carrying its record in the Next.js hydration payload."""
    games = [game] if game is not None else []
    payload = json.dumps({"props": {"pageProps": {"game": {"data": {"game": games}}}}})
    response = MagicMock()
    response.status_code = 200
    response.text = (
        '<html><body><script id="__NEXT_DATA__" type="application/json">'
        f"{payload}</script></body></html>"
    )
    return response


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_get_rom_by_id_reads_the_game_page(mock_ctx_httpx_client):
    """The by-ID lookup the manual edit form depends on: HLTB has no API for it,
    so the record comes off the game page."""
    handler = _handler()
    client = MagicMock()
    client.get = AsyncMock(return_value=_game_page(_game(7169, "Pokémon Red and Blue")))
    mock_ctx_httpx_client.get.return_value = client

    rom = await handler.get_rom_by_id(7169)

    assert rom["hltb_id"] == 7169
    assert rom["name"] == "Pokémon Red and Blue"
    assert rom["hltb_metadata"]["main_story"] == 3600
    assert rom["hltb_metadata"]["review_score"] == 70

    # The `/game?id=` form answers with a redirect the shared client won't follow.
    assert client.get.await_args.args[0] == "https://howlongtobeat.com/game/7169"


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_get_rom_by_id_sends_the_user_agent_hltb_requires(
    mock_ctx_httpx_client,
):
    handler = _handler()
    client = MagicMock()
    client.get = AsyncMock(return_value=_game_page(_game(7169, "Pokémon")))
    mock_ctx_httpx_client.get.return_value = client

    await handler.get_rom_by_id(7169)

    assert (
        client.get.await_args.kwargs["headers"]["User-Agent"] == f"RomM/{get_version()}"
    )


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_get_rom_by_id_reads_the_full_release_date(mock_ctx_httpx_client):
    """The game page dates a release in full where search returns just the year."""
    handler = _handler()
    game = _game(7169, "Pokémon Red and Blue") | {"release_world": "1996-02-27"}
    client = MagicMock()
    client.get = AsyncMock(return_value=_game_page(game))
    mock_ctx_httpx_client.get.return_value = client

    rom = await handler.get_rom_by_id(7169)

    assert rom["hltb_metadata"]["release_year"] == 1996


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_get_rom_by_id_tolerates_a_page_without_popularity(
    mock_ctx_httpx_client,
):
    """The game page omits the popularity search reports, so it must not fail."""
    handler = _handler()
    game = _game(7169, "Pokémon Red and Blue") | {"profile_popular": None}
    client = MagicMock()
    client.get = AsyncMock(return_value=_game_page(game))
    mock_ctx_httpx_client.get.return_value = client

    rom = await handler.get_rom_by_id(7169)

    assert rom["hltb_id"] == 7169
    assert "popularity" not in rom["hltb_metadata"]


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_unknown_id_is_not_reported_as_an_outage(mock_ctx_httpx_client):
    """A mistyped ID is the user's, not HLTB's, so it must not 503 the edit."""
    handler = _handler()
    client = MagicMock()
    client.get = AsyncMock(return_value=_response(status.HTTP_404_NOT_FOUND))
    mock_ctx_httpx_client.get.return_value = client

    rom = await handler.get_rom_by_id(999999999)

    assert rom["hltb_id"] is None


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_game_page_outage_reports_service_unavailable(mock_ctx_httpx_client):
    handler = _handler()
    client = MagicMock()
    client.get = AsyncMock(
        return_value=_response(status.HTTP_429_TOO_MANY_REQUESTS),
    )
    mock_ctx_httpx_client.get.return_value = client

    with pytest.raises(HTTPException) as exc_info:
        await handler.get_rom_by_id(7169)

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "rate limiting" in exc_info.value.detail


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_game_page_without_a_record_yields_no_match(mock_ctx_httpx_client):
    """An empty record list is HLTB answering honestly, not a rewrite."""
    handler = _handler()
    client = MagicMock()
    client.get = AsyncMock(return_value=_game_page(None))
    mock_ctx_httpx_client.get.return_value = client

    rom = await handler.get_rom_by_id(7169)

    assert rom["hltb_id"] is None


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_reshaped_game_page_reports_the_rewrite(mock_ctx_httpx_client):
    """A page RomM can no longer read has to say so: reported as a game with no
    times it is indistinguishable from the bug this lookup exists to fix."""
    handler = _handler()
    response = MagicMock()
    response.status_code = 200
    response.text = "<html><body>no hydration payload here</body></html>"
    client = MagicMock()
    client.get = AsyncMock(return_value=response)
    mock_ctx_httpx_client.get.return_value = client

    with pytest.raises(HTTPException) as exc_info:
        await handler.get_rom_by_id(7169)

    assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY
    assert "changed their game page" in exc_info.value.detail


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_renamed_game_fields_report_the_rewrite(mock_ctx_httpx_client):
    """Defaulting every field would quietly turn a rename into an empty match."""
    handler = _handler()
    client = MagicMock()
    client.get = AsyncMock(return_value=_game_page({"id": 7169, "name": "Pokémon"}))
    mock_ctx_httpx_client.get.return_value = client

    with pytest.raises(HTTPException) as exc_info:
        await handler.get_rom_by_id(7169)

    assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", False)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_get_rom_by_id_is_skipped_when_hltb_is_disabled(mock_ctx_httpx_client):
    rom = await _handler().get_rom_by_id(7169)

    assert rom["hltb_id"] is None
    mock_ctx_httpx_client.get.assert_not_called()


async def test_the_live_page_shape_still_parses():
    """Captured from howlongtobeat.com/game/7169. If HLTB reshapes the page this
    fixture goes stale, but it keeps our own parsing honest in the meantime."""
    fixture = Path(__file__).parent / "hltb_game_page_example.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))

    response = MagicMock()
    response.status_code = 200
    response.text = (
        '<script id="__NEXT_DATA__" type="application/json">'
        f"{json.dumps(payload)}</script>"
    )
    client = MagicMock()
    client.get = AsyncMock(return_value=response)

    with (
        patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True),
        patch("handler.metadata.hltb_handler.ctx_httpx_client") as ctx,
    ):
        ctx.get.return_value = client
        rom = await _handler().get_rom_by_id(7169)

    assert rom["hltb_id"] == 7169
    assert rom["name"] == "Pokémon Red and Blue"
    assert rom["url_cover"].endswith("7169_Pokmon_Red_and_Blue.png")
    assert rom["hltb_metadata"] == {
        "main_story": 92822,
        "main_story_count": 594,
        "main_plus_extra": 156016,
        "main_plus_extra_count": 378,
        "completionist": 354756,
        "completionist_count": 202,
        "all_styles": 139926,
        "all_styles_count": 1174,
        "release_year": 1996,
        "review_score": 81,
        "review_count": 1762,
        "completions": 5364,
    }


@pytest.mark.parametrize(
    "transport_error",
    [
        httpx.ConnectTimeout("timed out"),
        httpx.PoolTimeout("pool exhausted"),
        httpx.ReadError("reset"),
        httpx.RemoteProtocolError("bad framing"),
    ],
)
@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_transport_failures_report_service_unavailable(
    mock_ctx_httpx_client, transport_error
):
    """A slow or unreachable HLTB must not surface as a bare 500 on the rom edit."""
    handler = _handler()
    client = MagicMock()
    client.get = AsyncMock(side_effect=transport_error)
    mock_ctx_httpx_client.get.return_value = client

    with pytest.raises(HTTPException) as exc_info:
        await handler.get_rom_by_id(7169)

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "check your internet connection" in exc_info.value.detail


@pytest.mark.parametrize(
    ("label", "attributes"),
    [
        ("plain", 'id="__NEXT_DATA__" type="application/json"'),
        ("csp nonce", 'id="__NEXT_DATA__" type="application/json" nonce="r4nd0m"'),
        ("reordered", 'type="application/json" id="__NEXT_DATA__"'),
        ("single quotes", "id='__NEXT_DATA__' type='application/json'"),
        ("crossorigin", 'crossorigin="" id="__NEXT_DATA__" type="application/json"'),
    ],
)
@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_hydration_tag_is_found_however_it_is_marked_up(
    mock_ctx_httpx_client, label, attributes
):
    """Markup around the payload is not the contract; the id is. Reporting a
    rewrite over an added nonce would be a false alarm."""
    payload = json.dumps(
        {"props": {"pageProps": {"game": {"data": {"game": [_game(7169, "Pokémon")]}}}}}
    )
    response = MagicMock()
    response.status_code = 200
    response.text = f"<script {attributes}>{payload}</script>"
    client = MagicMock()
    client.get = AsyncMock(return_value=response)
    mock_ctx_httpx_client.get.return_value = client

    rom = await _handler().get_rom_by_id(7169)

    assert rom["hltb_id"] == 7169, label


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_a_redirect_is_followed_rather_than_read_as_a_rewrite(
    mock_ctx_httpx_client,
):
    """`raise_for_status` lets a 3xx through, so an unfollowed hop would reach
    the parser as a page with no payload and be blamed on HLTB reshaping it."""
    handler = _handler()
    client = MagicMock()
    client.get = AsyncMock(return_value=_game_page(_game(7169, "Pokémon")))
    mock_ctx_httpx_client.get.return_value = client

    await handler.get_rom_by_id(7169)

    assert client.get.await_args.kwargs["follow_redirects"] is True


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_an_unrelated_json_script_is_not_mistaken_for_the_payload(
    mock_ctx_httpx_client,
):
    """The looser tag match must not start picking up other JSON blocks."""
    handler = _handler()
    response = MagicMock()
    response.status_code = 200
    response.text = (
        '<script id="__OTHER_DATA__" type="application/json">{"game": []}</script>'
    )
    client = MagicMock()
    client.get = AsyncMock(return_value=response)
    mock_ctx_httpx_client.get.return_value = client

    with pytest.raises(HTTPException) as exc_info:
        await handler.get_rom_by_id(7169)

    assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY
