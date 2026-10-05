from collections.abc import AsyncIterator, Collection
from typing import Any, Literal, cast
from unittest.mock import AsyncMock, patch

import pytest

from adapters.services.steamgriddb import SteamGridDBService
from adapters.services.steamgriddb_types import (
    SGDBDimension,
    SGDBGame,
    SGDBGrid,
    SGDBMime,
    SGDBStyle,
    SGDBTag,
    SGDBType,
)
from handler.metadata import sgdb_handler
from handler.metadata.base_handler import CoverResult
from handler.metadata.sgdb_handler import SGDBBaseHandler


def _make_grid(**overrides):
    grid = {
        "id": 1,
        "score": 42,
        "style": "alternate",
        "width": 600,
        "height": 900,
        "nsfw": False,
        "humor": False,
        "epilepsy": False,
        "url": "https://cdn.example.com/grid/a.png",
        "thumb": "https://cdn.example.com/thumb/a.png",
        "author": {"name": "duckdicks", "steam64": "123", "avatar": ""},
    }
    grid.update(overrides)
    return grid


async def _aiter(items):
    for item in items:
        yield item


class TestGetGameCoversMapping:
    @pytest.mark.asyncio
    async def test_maps_rich_fields_onto_resource(self):
        handler = SGDBBaseHandler()
        with patch.object(
            handler.sgdb_service,
            "iter_grids_for_game",
            side_effect=lambda *a, **k: _aiter([_make_grid()]),
        ):
            result = await handler._get_game_covers(game_id=1, game_name="Test Game")

        assert result["name"] == "Test Game"
        assert len(result["resources"]) == 1
        resource = result["resources"][0]
        assert resource["width"] == 600
        assert resource["height"] == 900
        assert resource["style"] == "alternate"
        assert resource["author"] == "duckdicks"
        assert resource["score"] == 42
        assert resource["nsfw"] is False
        assert resource["type"] == "static"

    @pytest.mark.asyncio
    async def test_missing_optional_fields_default_safely(self):
        handler = SGDBBaseHandler()
        # A grid stripped of the optional metadata SGDB may omit.
        bare_grid = {
            "id": 2,
            "url": "https://cdn.example.com/grid/b.webm",
            "thumb": "https://cdn.example.com/thumb/b.webm",
        }
        with patch.object(
            handler.sgdb_service,
            "iter_grids_for_game",
            side_effect=lambda *a, **k: _aiter([bare_grid]),
        ):
            result = await handler._get_game_covers(game_id=2, game_name="Bare Game")

        resource = result["resources"][0]
        assert resource["width"] == 0
        assert resource["height"] == 0
        assert resource["style"] == ""
        assert resource["author"] == ""
        assert resource["score"] == 0
        assert resource["nsfw"] is False
        assert resource["humor"] is False
        assert resource["epilepsy"] is False
        # `.webm` thumbs are animated covers.
        assert resource["type"] == "animated"

    @pytest.mark.asyncio
    async def test_skips_dmca_locked_grids(self):
        handler = SGDBBaseHandler()
        grids = [
            _make_grid(id=1, lock=True, url="https://cdn.example.com/grid/locked.png?"),
            _make_grid(id=2, lock=False),
            _make_grid(id=3),
        ]
        with patch.object(
            handler.sgdb_service,
            "iter_grids_for_game",
            side_effect=lambda *a, **k: _aiter(grids),
        ):
            result = await handler._get_game_covers(game_id=1, game_name="Test Game")

        assert len(result["resources"]) == 2
        assert all("locked" not in resource["url"] for resource in result["resources"])

    @pytest.mark.asyncio
    async def test_all_locked_grids_yield_no_resources(self):
        handler = SGDBBaseHandler()
        with patch.object(
            handler.sgdb_service,
            "iter_grids_for_game",
            side_effect=lambda *a, **k: _aiter([_make_grid(lock=True)]),
        ):
            result = await handler._get_game_covers(game_id=1, game_name="Test Game")

        assert result == CoverResult(name="Test Game", resources=[])


class TestGetDetailsContentFilters:
    @pytest.mark.asyncio
    async def test_requests_all_content_variants(self):
        handler = SGDBBaseHandler()
        covers_mock = AsyncMock(
            return_value={"name": "Test Game", "resources": [_make_grid()]}
        )

        with (
            patch.object(
                handler.sgdb_service,
                "search_games",
                AsyncMock(return_value=[{"id": 7, "name": "Test Game"}]),
            ),
            patch.object(handler, "_get_game_covers", covers_mock),
            patch.object(SGDBBaseHandler, "is_enabled", return_value=True),
        ):
            await handler.get_details(search_term="test")

        covers_mock.assert_awaited_once()
        assert covers_mock.await_args is not None
        kwargs = covers_mock.await_args.kwargs
        assert kwargs["is_nsfw"] == "any"
        assert kwargs["is_humor"] == "any"
        assert kwargs["is_epilepsy"] == "any"


class TestLookupFailures:
    @pytest.mark.asyncio
    async def test_get_details_by_names_propagates_an_unreachable_sgdb(self):
        """A failed lookup has to stay distinguishable from a name with no art."""
        handler = SGDBBaseHandler()

        with (
            patch.object(
                handler.sgdb_service,
                "search_games",
                AsyncMock(side_effect=RuntimeError("SteamGridDB is down")),
            ),
            patch.object(SGDBBaseHandler, "is_enabled", return_value=True),
            pytest.raises(RuntimeError),
        ):
            await handler.get_details_by_names(["Test Game"])

    @pytest.mark.asyncio
    async def test_get_rom_by_id_propagates_an_unreachable_sgdb(self):
        handler = SGDBBaseHandler()

        with (
            patch.object(
                handler.sgdb_service,
                "get_game_by_id",
                AsyncMock(side_effect=RuntimeError("SteamGridDB is down")),
            ),
            patch.object(SGDBBaseHandler, "is_enabled", return_value=True),
            pytest.raises(RuntimeError),
        ):
            await handler.get_rom_by_id(7)


class FakeSGDB(SteamGridDBService):
    """Answers searches, game lookups and grid listings from fixed data."""

    def __init__(self) -> None:
        super().__init__()
        self.searches: dict[str, list[SGDBGame]] = {}
        self.games: dict[int, SGDBGame] = {}
        self.grids: dict[int, list[dict[str, Any]]] = {}
        self.terms: list[str] = []
        self.grid_queries: list[dict[str, Any]] = []

    async def search_games(self, term: str) -> list[SGDBGame]:
        self.terms.append(term)
        return self.searches.get(term, [])

    async def get_game_by_id(self, game_id: int) -> SGDBGame | None:
        return self.games.get(game_id)

    async def iter_grids_for_game(
        self,
        game_id: int,
        *,
        styles: Collection[SGDBStyle] | None = None,
        dimensions: Collection[SGDBDimension] | None = None,
        mimes: Collection[SGDBMime] | None = None,
        types: Collection[SGDBType] | None = None,
        any_of_tags: Collection[SGDBTag] | None = None,
        is_nsfw: bool | Literal["any"] | None = None,
        is_humor: bool | Literal["any"] | None = None,
        is_epilepsy: bool | Literal["any"] | None = None,
    ) -> AsyncIterator[SGDBGrid]:
        self.grid_queries.append(
            {
                "game_id": game_id,
                "types": types,
                "is_nsfw": is_nsfw,
                "is_humor": is_humor,
                "is_epilepsy": is_epilepsy,
            }
        )
        for grid in self.grids.get(game_id, []):
            yield cast(SGDBGrid, grid)


def _game(game_id: int, name: str) -> SGDBGame:
    return SGDBGame(id=game_id, name=name, types=["steam"], verified=True)


@pytest.fixture
def sgdb(monkeypatch: pytest.MonkeyPatch) -> tuple[SGDBBaseHandler, FakeSGDB]:
    monkeypatch.setattr(sgdb_handler, "STEAMGRIDDB_API_KEY", "key")
    handler = SGDBBaseHandler()
    fake = FakeSGDB()
    handler.sgdb_service = fake
    return handler, fake


SAFE_STATIC = {
    "types": (SGDBType.STATIC,),
    "is_nsfw": False,
    "is_humor": False,
    "is_epilepsy": False,
}


class TestHeartbeat:
    async def test_a_known_game_is_healthy(
        self, sgdb: tuple[SGDBBaseHandler, FakeSGDB]
    ):
        handler, fake = sgdb
        fake.games[1] = _game(1, "Half-Life")

        assert await handler.heartbeat() is True

    async def test_no_game_is_unhealthy(self, sgdb: tuple[SGDBBaseHandler, FakeSGDB]):
        handler, _ = sgdb

        assert await handler.heartbeat() is False

    async def test_an_error_is_unhealthy(
        self, sgdb: tuple[SGDBBaseHandler, FakeSGDB], monkeypatch: pytest.MonkeyPatch
    ):
        handler, fake = sgdb
        monkeypatch.setattr(
            fake, "get_game_by_id", AsyncMock(side_effect=RuntimeError("down"))
        )

        assert await handler.heartbeat() is False

    async def test_without_a_key_nothing_is_asked(
        self, sgdb: tuple[SGDBBaseHandler, FakeSGDB], monkeypatch: pytest.MonkeyPatch
    ):
        handler, fake = sgdb
        monkeypatch.setattr(sgdb_handler, "STEAMGRIDDB_API_KEY", "")
        lookup = AsyncMock()
        monkeypatch.setattr(fake, "get_game_by_id", lookup)

        assert await handler.heartbeat() is False
        assert await handler.get_rom_by_id(1) == {"sgdb_id": None}
        assert await handler.get_details("Half-Life") == []
        assert await handler.get_details_by_names(["Half-Life"]) == {"sgdb_id": None}
        lookup.assert_not_awaited()
        assert fake.terms == []


class TestGetRomById:
    async def test_takes_the_first_cover_with_a_url(
        self, sgdb: tuple[SGDBBaseHandler, FakeSGDB]
    ):
        handler, fake = sgdb
        fake.games[7] = _game(7, "Half-Life")
        fake.grids[7] = [_make_grid(url=""), _make_grid(id=2, url="https://g/2.png")]

        assert await handler.get_rom_by_id(7) == {
            "sgdb_id": 7,
            "url_cover": "https://g/2.png",
        }
        [query] = fake.grid_queries
        assert {k: query[k] for k in SAFE_STATIC} == SAFE_STATIC

    async def test_a_game_without_covers_has_no_cover(
        self, sgdb: tuple[SGDBBaseHandler, FakeSGDB]
    ):
        handler, fake = sgdb
        fake.games[7] = _game(7, "Half-Life")

        assert await handler.get_rom_by_id(7) == {"sgdb_id": 7}

    async def test_an_unknown_game_is_no_match(
        self, sgdb: tuple[SGDBBaseHandler, FakeSGDB]
    ):
        handler, _ = sgdb

        assert await handler.get_rom_by_id(7) == {"sgdb_id": None}


class TestGetDetails:
    async def test_lists_each_found_games_covers(
        self, sgdb: tuple[SGDBBaseHandler, FakeSGDB]
    ):
        handler, fake = sgdb
        fake.searches["half"] = [_game(1, "Half-Life"), _game(2, "Half-Life 2")]
        fake.grids[1] = [_make_grid()]

        results = await handler.get_details("half")

        assert [(r["name"], len(r["resources"])) for r in results] == [
            ("Half-Life", 1),
            ("Half-Life 2", 0),
        ]

    async def test_nothing_found_is_empty(self, sgdb: tuple[SGDBBaseHandler, FakeSGDB]):
        handler, _ = sgdb

        assert await handler.get_details("nothing") == []


class TestGetDetailsByNames:
    async def test_matches_the_first_name_found(
        self, sgdb: tuple[SGDBBaseHandler, FakeSGDB]
    ):
        handler, fake = sgdb
        fake.searches["half life 2"] = [_game(2, "Half-Life 2")]
        fake.grids[2] = [_make_grid(url="https://g/hl2.png")]

        result = await handler.get_details_by_names(["Half-Life: 2"])

        assert result == {"sgdb_id": 2, "url_cover": "https://g/hl2.png"}
        # The search is lowercased without punctuation.
        assert fake.terms == ["half life 2"]
        [query] = fake.grid_queries
        assert {k: query[k] for k in SAFE_STATIC} == SAFE_STATIC

    async def test_tries_the_next_name_when_one_finds_nothing(
        self, sgdb: tuple[SGDBBaseHandler, FakeSGDB]
    ):
        handler, fake = sgdb
        fake.searches["the game"] = [_game(3, "The Game")]
        fake.grids[3] = [_make_grid(url="https://g/3.png")]

        result = await handler.get_details_by_names(["Unknown", "The Game"])

        assert result["sgdb_id"] == 3
        # Articles stay in the search.
        assert fake.terms == ["unknown", "the game"]

    async def test_of_games_sharing_a_name_the_oldest_wins(
        self, sgdb: tuple[SGDBBaseHandler, FakeSGDB]
    ):
        handler, fake = sgdb
        fake.searches["doom"] = [_game(9, "Doom"), _game(4, "Doom"), _game(6, "Doom")]
        fake.grids[4] = [_make_grid(url="https://g/4.png")]

        assert (await handler.get_details_by_names(["Doom"]))["sgdb_id"] == 4

    async def test_a_match_without_covers_moves_on(
        self, sgdb: tuple[SGDBBaseHandler, FakeSGDB]
    ):
        handler, fake = sgdb
        fake.searches["doom"] = [_game(4, "Doom")]
        fake.searches["doom ii"] = [_game(5, "Doom II")]
        fake.grids[5] = [_make_grid(url="https://g/5.png")]

        result = await handler.get_details_by_names(["Doom", "Doom II"])

        assert result == {"sgdb_id": 5, "url_cover": "https://g/5.png"}

    async def test_a_loose_match_is_no_match(
        self, sgdb: tuple[SGDBBaseHandler, FakeSGDB]
    ):
        handler, fake = sgdb
        fake.searches["doom"] = [_game(4, "Doom Eternal")]
        fake.grids[4] = [_make_grid()]

        assert await handler.get_details_by_names(["Doom"]) == {"sgdb_id": None}
