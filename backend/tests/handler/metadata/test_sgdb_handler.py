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
