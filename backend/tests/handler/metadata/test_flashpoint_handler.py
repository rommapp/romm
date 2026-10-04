"""Tests for the Flashpoint handler's lookup failure reporting."""

import time
from collections.abc import AsyncIterator
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import httpx2
import pytest
from fastapi import HTTPException

from handler.metadata import flashpoint_handler
from handler.metadata.flashpoint_handler import (
    FlashpointGame,
    FlashpointHandler,
    extract_flashpoint_metadata,
)
from utils.context import ctx_httpx_client


@pytest.mark.asyncio
async def test_search_games_propagates_an_unreachable_flashpoint():
    """A failed search has to stay distinguishable from a term with no hits."""
    handler = FlashpointHandler()

    with (
        patch.object(FlashpointHandler, "is_enabled", return_value=True),
        patch.object(
            FlashpointHandler,
            "_request",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=503, detail="down"),
        ),
        pytest.raises(HTTPException),
    ):
        await handler.search_games("Interactive Buddy")


@pytest.mark.asyncio
async def test_get_rom_by_id_propagates_an_unreachable_flashpoint():
    handler = FlashpointHandler()

    with (
        patch("handler.metadata.flashpoint_handler.FLASHPOINT_API_ENABLED", True),
        patch.object(
            FlashpointHandler,
            "_request",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=503, detail="down"),
        ),
        pytest.raises(HTTPException),
    ):
        await handler.get_rom_by_id("dc1f7d99-9a3d-4f3f-8f2a-000000000000")


GAME_ID = "1f2e3d4c-5b6a-4987-8a7b-6c5d4e3f2a1b"


def _api_game(**overrides: Any) -> dict[str, Any]:
    return {
        "id": GAME_ID,
        "title": "Interactive Buddy",
        "originalDescription": "Poke the buddy.",
        "platform": "Flash",
        "library": "arcade",
        "series": "Buddy",
        "developer": "Shock Value",
        "publisher": "Shock Value",
        "source": "Newgrounds",
        "tags": ["Simulation", "Toy"],
        "dateAdded": "2018-01-01",
        "dateModified": "2019-01-01",
        "playMode": "Single Player",
        "status": "Playable",
        "version": "1.0",
        "releaseDate": "2005-03-14",
        "language": "en",
        "notes": "",
        **overrides,
    }


class FakeFlashpoint:
    """Answers the Flashpoint API through a real httpx2 client."""

    def __init__(self) -> None:
        self.requests: list[httpx2.Request] = []
        self.search_results: list[dict[str, Any]] = [_api_game()]
        self.status = 200
        self.body: bytes | None = None

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if self.body is not None:
            return httpx2.Response(self.status, content=self.body)
        if request.url.path == "/platforms":
            return httpx2.Response(self.status, json=[{"id": 1, "name": "Flash"}])
        return httpx2.Response(self.status, json=self.search_results)

    @property
    def queries(self) -> list[dict[str, str]]:
        return [dict(r.url.params) for r in self.requests]


@pytest.fixture
async def api(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[FakeFlashpoint]:
    monkeypatch.setattr(flashpoint_handler, "FLASHPOINT_API_ENABLED", True)
    fake = FakeFlashpoint()
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(fake))
    token = ctx_httpx_client.set(client)
    try:
        yield fake
    finally:
        ctx_httpx_client.reset(token)
        await client.aclose()


@pytest.fixture
def handler() -> FlashpointHandler:
    return FlashpointHandler()


def _art(kind: str) -> str:
    return f"https://infinity.unstable.life/images/{kind}/1f/2e/{GAME_ID}?type=jpg"


class TestRequest:
    async def test_drops_empty_query_values_and_names_romm(
        self, handler: FlashpointHandler, api: FakeFlashpoint
    ):
        await handler._request(
            handler.search_url, {"smartSearch": "buddy", "id": None, "filter": ""}
        )

        [request] = api.requests
        assert dict(request.url.params) == {"smartSearch": "buddy"}
        assert request.headers["user-agent"].startswith("RomM/")

    async def test_a_server_error_means_unavailable(
        self, handler: FlashpointHandler, api: FakeFlashpoint
    ):
        api.status = 502

        with pytest.raises(HTTPException) as exc:
            await handler._request(handler.search_url, {})

        assert exc.value.status_code == 503

    async def test_a_body_that_is_not_json_is_empty(
        self, handler: FlashpointHandler, api: FakeFlashpoint
    ):
        api.body = b"<html>maintenance</html>"

        assert await handler._request(handler.search_url, {}) == {}


class TestHeartbeat:
    async def test_reachable(self, handler: FlashpointHandler, api: FakeFlashpoint):
        assert await handler.heartbeat()

    async def test_unreachable(self, handler: FlashpointHandler, api: FakeFlashpoint):
        api.status = 500

        assert not await handler.heartbeat()

    async def test_an_empty_answer_is_down(
        self, handler: FlashpointHandler, api: FakeFlashpoint
    ):
        api.body = b"[]"

        assert not await handler.heartbeat()

    async def test_disabled_sends_nothing(
        self,
        handler: FlashpointHandler,
        api: FakeFlashpoint,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(flashpoint_handler, "FLASHPOINT_API_ENABLED", False)

        assert not await handler.heartbeat()
        assert api.requests == []


class TestGetPlatform:
    def test_browser_is_flashpoints_only_platform(self, handler: FlashpointHandler):
        assert handler.get_platform("browser") == {
            "slug": "browser",
            "name": "Browser (Flash/HTML5)",
            "flashpoint_id": 1,
        }

    def test_any_other_platform_is_unknown(self, handler: FlashpointHandler):
        assert handler.get_platform("gba") == {"slug": "gba", "flashpoint_id": None}


class TestGetRom:
    async def test_matches_by_title_and_maps_the_game(
        self, handler: FlashpointHandler, api: FakeFlashpoint
    ):
        api.search_results = [
            _api_game(id="aaaaaaaa-0000-4000-8000-000000000000", title="Bubble Tanks"),
            _api_game(),
        ]

        rom = await handler.get_rom("Interactive Buddy (2005).swf", "browser")

        assert api.queries == [{"smartSearch": "interactive buddy", "filter": "false"}]
        assert rom == {
            "flashpoint_id": GAME_ID,
            "name": "Interactive Buddy",
            "summary": "Poke the buddy.",
            "url_cover": _art("Logos"),
            "url_screenshots": [_art("Screenshots")],
            "flashpoint_metadata": {
                "franchises": ["Buddy"],
                "companies": ["Shock Value"],
                "publishers": ["Shock Value"],
                "developers": ["Shock Value"],
                "source": "Newgrounds",
                "genres": ["Simulation", "Toy"],
                "first_release_date": "1110758400",
                "game_modes": ["Single Player"],
                "status": "Playable",
                "version": "1.0",
                "language": "en",
                "notes": "",
            },
        }

    async def test_a_uuid_in_the_file_name_is_looked_up_by_id(
        self, handler: FlashpointHandler, api: FakeFlashpoint
    ):
        rom = await handler.get_rom(f"{GAME_ID}.swf", "browser")

        assert api.queries == [{"id": GAME_ID, "filter": "false"}]
        assert rom["flashpoint_id"] == GAME_ID

    async def test_a_weak_match_is_no_match(
        self, handler: FlashpointHandler, api: FakeFlashpoint
    ):
        api.search_results = [_api_game(title="Something Else Entirely")]

        rom = await handler.get_rom("Interactive Buddy.swf", "browser")

        assert rom == {"flashpoint_id": None}

    async def test_no_results_is_no_match(
        self, handler: FlashpointHandler, api: FakeFlashpoint
    ):
        api.search_results = []

        assert await handler.get_rom("Interactive Buddy.swf", "browser") == {
            "flashpoint_id": None
        }

    async def test_other_platforms_are_not_searched(
        self, handler: FlashpointHandler, api: FakeFlashpoint
    ):
        assert await handler.get_rom("Zelda.gba", "gba") == {"flashpoint_id": None}
        assert api.requests == []

    async def test_disabled_is_not_searched(
        self,
        handler: FlashpointHandler,
        api: FakeFlashpoint,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(flashpoint_handler, "FLASHPOINT_API_ENABLED", False)

        assert await handler.get_rom("Interactive Buddy.swf", "browser") == {
            "flashpoint_id": None
        }
        assert api.requests == []


class TestGetMatchedRomsByName:
    async def test_returns_every_result(
        self, handler: FlashpointHandler, api: FakeFlashpoint
    ):
        other_id = "aaaaaaaa-0000-4000-8000-000000000000"
        api.search_results = [_api_game(), _api_game(id=other_id, title="Buddy 2")]

        roms = await handler.get_matched_roms_by_name("buddy.swf", "browser")

        assert [rom["flashpoint_id"] for rom in roms] == [GAME_ID, other_id]
        assert roms[0].get("url_cover") == _art("Logos")

    async def test_other_platforms_are_not_searched(
        self, handler: FlashpointHandler, api: FakeFlashpoint
    ):
        assert await handler.get_matched_roms_by_name("buddy.swf", "gba") == []
        assert api.requests == []


class TestGetRomById:
    async def test_maps_the_game(self, handler: FlashpointHandler, api: FakeFlashpoint):
        rom = await handler.get_rom_by_id(GAME_ID)

        assert rom.get("name") == "Interactive Buddy"
        assert rom.get("url_screenshots") == [_art("Screenshots")]

    @pytest.mark.parametrize(
        "results",
        [[], [["not", "a", "game"]], [_api_game(id="")]],
        ids=["no_results", "not_an_object", "no_id"],
    )
    async def test_an_unusable_answer_is_no_match(
        self,
        handler: FlashpointHandler,
        api: FakeFlashpoint,
        results: list[Any],
    ):
        api.search_results = results

        assert await handler.get_rom_by_id(GAME_ID) == {"flashpoint_id": None}

    async def test_no_id_sends_nothing(
        self, handler: FlashpointHandler, api: FakeFlashpoint
    ):
        assert await handler.get_rom_by_id("") == {"flashpoint_id": None}
        assert api.requests == []


class TestExtractFlashpointMetadata:
    def _game(self, **overrides: Any) -> FlashpointGame:
        game = {
            "id": GAME_ID,
            "title": "Interactive Buddy",
            "original_description": "",
            "platform": "Flash",
            "library": "arcade",
            "series": "",
            "developer": "Shock Value",
            "publisher": "Newgrounds",
            "source": "",
            "tags": [],
            "date_added": "",
            "date_modified": "",
            "play_mode": "",
            "status": "",
            "version": "",
            "release_date": "2005-03-14",
            "language": "",
            "notes": "",
            **overrides,
        }
        return cast(FlashpointGame, game)

    def test_lists_developer_and_publisher_as_companies(self):
        metadata = extract_flashpoint_metadata(self._game())

        assert metadata["companies"] == ["Shock Value", "Newgrounds"]
        assert (metadata["franchises"], metadata["game_modes"]) == ([], [])

    @pytest.mark.parametrize("release_date", ["", "March 2005", "2005-13-01"])
    def test_an_unreadable_release_date_is_empty(self, release_date: str):
        metadata = extract_flashpoint_metadata(self._game(release_date=release_date))

        assert metadata["first_release_date"] == ""

    def test_the_release_date_does_not_depend_on_the_server_timezone(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("TZ", "America/Los_Angeles")
        time.tzset()
        try:
            metadata = extract_flashpoint_metadata(self._game())
        finally:
            monkeypatch.undo()
            time.tzset()

        assert metadata["first_release_date"] == "1110758400"
