from unittest.mock import AsyncMock, patch

import pytest

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

        assert result == {"name": "Test Game", "resources": []}


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


def _page(*grids):
    return {"page": 0, "total": len(grids), "limit": 10, "data": list(grids)}


class TestGetSteamArtwork:
    @pytest.mark.asyncio
    async def test_picks_the_highest_scoring_unlocked_asset(self):
        handler = SGDBBaseHandler()
        heroes = _page(
            _make_grid(score=10, url="https://cdn.example.com/hero/low.png"),
            _make_grid(score=99, url="https://cdn.example.com/hero/best.png"),
            # A locked asset serves a takedown placeholder, whatever it scores.
            _make_grid(
                score=100, lock=True, url="https://cdn.example.com/hero/locked.png"
            ),
        )
        logos = _page(_make_grid(score=5, url="https://cdn.example.com/logo/a.png"))

        with (
            patch.object(handler, "is_enabled", return_value=True),
            patch.object(
                handler.sgdb_service,
                "get_heroes_for_game",
                AsyncMock(return_value=heroes),
            ),
            patch.object(
                handler.sgdb_service,
                "get_logos_for_game",
                AsyncMock(return_value=logos),
            ),
        ):
            result = await handler.get_steam_artwork(1)

        assert result["url_hero"] == "https://cdn.example.com/hero/best.png"
        assert result["url_logo"] == "https://cdn.example.com/logo/a.png"

    @pytest.mark.asyncio
    async def test_missing_artwork_is_null_not_an_error(self):
        handler = SGDBBaseHandler()
        with (
            patch.object(handler, "is_enabled", return_value=True),
            patch.object(
                handler.sgdb_service,
                "get_heroes_for_game",
                AsyncMock(return_value=_page()),
            ),
            patch.object(
                handler.sgdb_service,
                "get_logos_for_game",
                AsyncMock(return_value=_page()),
            ),
        ):
            assert await handler.get_steam_artwork(1) == {
                "url_hero": None,
                "url_logo": None,
            }

    @pytest.mark.asyncio
    async def test_a_failed_lookup_degrades_to_null(self):
        handler = SGDBBaseHandler()
        with (
            patch.object(handler, "is_enabled", return_value=True),
            patch.object(
                handler.sgdb_service,
                "get_heroes_for_game",
                AsyncMock(side_effect=RuntimeError("SteamGridDB is down")),
            ),
            patch.object(
                handler.sgdb_service,
                "get_logos_for_game",
                AsyncMock(return_value=_page()),
            ),
        ):
            assert await handler.get_steam_artwork(1) == {
                "url_hero": None,
                "url_logo": None,
            }

    @pytest.mark.asyncio
    async def test_without_an_api_key_nothing_is_requested(self):
        handler = SGDBBaseHandler()
        heroes = AsyncMock()
        with (
            patch.object(handler, "is_enabled", return_value=False),
            patch.object(handler.sgdb_service, "get_heroes_for_game", heroes),
        ):
            assert await handler.get_steam_artwork(1) == {
                "url_hero": None,
                "url_logo": None,
            }
        heroes.assert_not_awaited()
