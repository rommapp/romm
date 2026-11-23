"""HowLongToBeat paths the main suite leaves out, driven through a real httpx2
client: search results, the picker list, transport failures, and the game page
when its payload no longer parses."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx2
import pytest
import pytest_asyncio
from fastapi import HTTPException, status

from handler.metadata import hltb_handler
from handler.metadata.hltb_handler import (
    HLTB_FORMAT_CHANGED_DETAIL,
    HLTBHandler,
    _release_year,
    _unavailable_detail,
)
from utils.context import ctx_httpx_client
from utils.hltb_search import SESSION_MINT_SUFFIX

SEARCH_URL = "https://howlongtobeat.com/api/search"


class HLTBStub:
    """Answers HowLongToBeat requests, scripting each reply."""

    def __init__(self) -> None:
        self.replies: list[httpx2.Response | Exception] = []
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest_asyncio.fixture
async def hltb(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[HLTBHandler, HLTBStub]]:
    monkeypatch.setattr(hltb_handler, "HLTB_API_ENABLED", True)
    monkeypatch.setattr(hltb_handler._rate_limiter, "acquire", AsyncMock())
    # Swap only this module's reference, so httpx2 keeps its real sleep.
    monkeypatch.setattr(
        "handler.metadata.hltb_handler.asyncio",
        MagicMock(wraps=asyncio, sleep=AsyncMock()),
    )
    handler = HLTBHandler()
    handler.search_url = SEARCH_URL
    handler.search_init_url = f"{SEARCH_URL}{SESSION_MINT_SUFFIX}"
    handler.security_token = "token"
    handler.hp_key = "ign_key"
    handler.hp_val = "value"
    stub = HLTBStub()
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(stub))
    token = ctx_httpx_client.set(client)
    try:
        yield handler, stub
    finally:
        ctx_httpx_client.reset(token)
        await client.aclose()


def _json(body: object, status_code: int = 200) -> httpx2.Response:
    return httpx2.Response(status_code, json=body)


def _game(game_id: int, name: str) -> dict[str, Any]:
    return {
        "game_id": game_id,
        "game_name": name,
        "game_image": f"{game_id}.jpg",
        "comp_main": 3600,
        "comp_main_count": 1,
        "release_world": 1998,
    }


class TestSearch:
    async def test_reads_each_game_with_an_id(self, hltb: tuple[HLTBHandler, HLTBStub]):
        handler, stub = hltb
        stub.replies = [
            _json({"data": [_game(1, "Zelda"), {"game_name": "no id"}, "junk"]})
        ]

        games = await handler.search_games("zelda", "n64")

        assert [(g["game_id"], g["game_name"]) for g in games] == [(1, "Zelda")]
        assert stub.requests[0].method == "POST"

    @pytest.mark.parametrize(
        "body",
        [{}, {"data": {"game_id": 1}}, {"count": 0}],
        ids=["empty", "data_not_a_list", "data_absent"],
    )
    async def test_an_unusable_answer_has_no_games(
        self, hltb: tuple[HLTBHandler, HLTBStub], body: dict[str, Any]
    ):
        handler, stub = hltb
        stub.replies = [_json(body)]

        assert await handler.search_games("zelda", "n64") == []

    async def test_a_reply_that_is_not_json_has_no_games(
        self, hltb: tuple[HLTBHandler, HLTBStub]
    ):
        handler, stub = hltb
        stub.replies = [httpx2.Response(200, content=b"<html>")]

        assert await handler.search_games("zelda", "n64") == []

    @pytest.mark.parametrize(
        "error",
        [
            httpx2.ConnectError("no route"),
            httpx2.ConnectTimeout("timed out"),
            httpx2.PoolTimeout("pool exhausted"),
            httpx2.ReadError("reset"),
            httpx2.ReadTimeout("slow"),
            httpx2.RemoteProtocolError("bad framing"),
        ],
        ids=["refused", "connect_timeout", "pool", "reset", "read_timeout", "dropped"],
    )
    async def test_a_transport_failure_is_unavailable(
        self, hltb: tuple[HLTBHandler, HLTBStub], error: Exception
    ):
        handler, stub = hltb
        stub.replies = [error]

        with pytest.raises(HTTPException) as exc:
            await handler.search_games("zelda", "n64")

        assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "internet connection" in exc.value.detail


class TestMatchedByName:
    async def test_lists_every_result(self, hltb: tuple[HLTBHandler, HLTBStub]):
        handler, stub = hltb
        stub.replies = [_json({"data": [_game(1, "Zelda"), _game(2, "Zelda II")]})]

        roms = await handler.get_matched_roms_by_name("Zelda (USA).z64", "n64")

        assert [(r["hltb_id"], r.get("url_cover")) for r in roms] == [
            (1, "https://howlongtobeat.com/games/1.jpg"),
            (2, "https://howlongtobeat.com/games/2.jpg"),
        ]

    async def test_disabled_asks_nothing(
        self, hltb: tuple[HLTBHandler, HLTBStub], monkeypatch: pytest.MonkeyPatch
    ):
        handler, stub = hltb
        monkeypatch.setattr(hltb_handler, "HLTB_API_ENABLED", False)

        assert await handler.get_matched_roms_by_name("Zelda.z64", "n64") == []
        assert await handler.get_rom("Zelda.z64", "n64") == {"hltb_id": None}
        assert await handler.heartbeat() is False
        await handler._fetch_search_endpoint()
        await handler._fetch_security_token()
        assert stub.requests == []

    def test_an_unknown_platform_has_no_hltb_slug(self):
        assert HLTBHandler().get_platform("not-a-platform") == {
            "slug": "not-a-platform",
            "hltb_slug": None,
        }


class TestHeartbeat:
    @pytest.mark.parametrize(
        ("reply", "healthy"),
        [
            (_json({}), True),
            (_json({}, status_code=500), False),
            (httpx2.ConnectError("down"), False),
        ],
        ids=["answers", "error", "down"],
    )
    async def test_reports_whether_hltb_answers(
        self,
        hltb: tuple[HLTBHandler, HLTBStub],
        reply: httpx2.Response | Exception,
        healthy: bool,
    ):
        handler, stub = hltb
        stub.replies = [reply]

        assert await handler.heartbeat() is healthy


class TestSessionMint:
    async def test_a_failed_mint_leaves_no_session(
        self, hltb: tuple[HLTBHandler, HLTBStub]
    ):
        handler, stub = hltb
        stub.replies = [httpx2.ConnectError("down")]

        await handler._fetch_security_token()

        assert stub.requests[0].url.path.endswith(SESSION_MINT_SUFFIX)
        assert (handler.security_token, handler.hp_key) == ("token", "ign_key")


def _page(script: str) -> httpx2.Response:
    return httpx2.Response(200, text=f"<html>{script}</html>")


class TestGamePageRewrites:
    @pytest.mark.parametrize(
        "script",
        [
            '<script id="__NEXT_DATA__" type="application/json">{not json</script>',
            '<script id="__NEXT_DATA__" type="application/json">'
            '{"props": {"pageProps": {"game": {"data": {"game": {}}}}}}</script>',
        ],
        ids=["not_json", "no_game_list"],
    )
    async def test_a_payload_that_no_longer_parses_is_reported(
        self, hltb: tuple[HLTBHandler, HLTBStub], script: str
    ):
        handler, stub = hltb
        stub.replies = [_page(script)]

        with pytest.raises(HTTPException) as exc:
            await handler.get_rom_by_id(7169)

        assert exc.value.status_code == status.HTTP_502_BAD_GATEWAY
        assert exc.value.detail == HLTB_FORMAT_CHANGED_DETAIL


@pytest.mark.parametrize(
    ("value", "year"),
    [(1998, 1998), ("1998-11-21", 1998), ("TBA", 0), (None, 0)],
)
def test_release_year(value: object, year: int):
    assert _release_year(value) == year


def test_an_unexpected_status_is_named():
    assert _unavailable_detail(502) == "HowLongToBeat API returned HTTP 502"
