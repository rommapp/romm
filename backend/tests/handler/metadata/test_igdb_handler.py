"""Tests for the IGDB metadata handler."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.services.igdb_types import GameType
from handler.metadata.igdb_handler import IGDBHandler


GENESIS_IGDB_ID = 29


def _make_game(game_id: int, name: str) -> dict:
    """Build a minimal IGDB Game dict for testing."""
    return {
        "id": game_id,
        "name": name,
        "slug": name.lower().replace(" ", "-"),
        "summary": "",
        "total_rating": 0.0,
        "aggregated_rating": 0.0,
        "first_release_date": None,
        "artworks": [],
        "cover": None,
        "screenshots": [],
        "platforms": [{"id": GENESIS_IGDB_ID, "name": "Sega Mega Drive/Genesis"}],
        "alternative_names": [],
        "genres": [],
        "franchise": None,
        "franchises": [],
        "collections": [],
        "game_modes": [],
        "involved_companies": [],
        "expansions": [],
        "dlcs": [],
        "remasters": [],
        "remakes": [],
        "expanded_games": [],
        "ports": [],
        "similar_games": [],
        "videos": [],
        "age_ratings": [],
        "multiplayer_modes": [],
        "game_localizations": [],
    }


class TestSearchRomGameTypeFilter:
    """Tests for _search_rom game_type filtering."""

    @pytest.mark.asyncio
    async def test_standalone_expansion_included_in_game_type_filter(self):
        """Searching with game_type filter must include STANDALONE_EXPANSION
        so that games like 'Ecco: The Tides of Time' are found on the first
        search pass and not confused with their parent game."""
        handler = IGDBHandler()

        ecco_dolphin = _make_game(1799, "Ecco the Dolphin")
        ecco_tides = _make_game(5379, "Ecco: The Tides of Time")

        async def mock_list_games(
            search_term=None, fields=None, where=None, limit=None
        ):
            # First call (with game_type filter): return both games
            if where and "game_type" in where:
                # Verify STANDALONE_EXPANSION (4) is in the filter
                assert (
                    str(int(GameType.STANDALONE_EXPANSION)) in where
                ), f"STANDALONE_EXPANSION should be in game_type filter, got: {where}"
                # Simulate IGDB returning both games when the search includes
                # standalone expansions
                if search_term and "tides of time" in search_term.lower():
                    return [ecco_dolphin, ecco_tides]
                return [ecco_dolphin]
            return []

        with (
            patch(
                "handler.metadata.igdb_handler.IGDBHandler.is_enabled",
                return_value=True,
            ),
            patch.object(
                handler.igdb_service,
                "list_games",
                side_effect=mock_list_games,
            ),
            patch.object(
                handler.igdb_service,
                "search",
                return_value=[],
            ),
        ):
            result = await handler._search_rom(
                "ecco the tides of time", GENESIS_IGDB_ID, with_game_type=True
            )

        assert result is not None
        assert result["id"] == 5379, (
            f"Expected Ecco: The Tides of Time (id=5379), got {result.get('name')} (id={result.get('id')})"
        )

    @pytest.mark.asyncio
    async def test_expanded_search_uses_all_results_not_just_first(self):
        """When the primary search fails and the expanded IGDB search endpoint
        is used, all unique game IDs from the results must be fetched and
        the best match selected — not just the first result."""
        handler = IGDBHandler()

        ecco_dolphin = _make_game(1799, "Ecco the Dolphin")
        ecco_tides = _make_game(5379, "Ecco: The Tides of Time")

        # Primary search returns nothing useful
        async def mock_list_games(
            search_term=None, fields=None, where=None, limit=None
        ):
            if where and "game_type" not in where and not where.startswith("("):
                # Primary search pass — return no results so we fall through to
                # the expanded search
                return []
            if where and where.startswith("("):
                # Expanded game details lookup — return both candidates
                return [ecco_dolphin, ecco_tides]
            return []

        # Expanded search returns two results — wrong game FIRST, correct game second
        expanded_results = [
            {"game": {"id": 1799}, "name": "Ecco the Dolphin"},
            {"game": {"id": 5379}, "name": "Ecco: The Tides of Time"},
        ]

        with (
            patch(
                "handler.metadata.igdb_handler.IGDBHandler.is_enabled",
                return_value=True,
            ),
            patch.object(
                handler.igdb_service,
                "list_games",
                side_effect=mock_list_games,
            ),
            patch.object(
                handler.igdb_service,
                "search",
                return_value=expanded_results,
            ),
        ):
            result = await handler._search_rom(
                "ecco the tides of time", GENESIS_IGDB_ID, with_game_type=False
            )

        assert result is not None
        assert result["id"] == 5379, (
            f"Expected Ecco: The Tides of Time (id=5379), got {result.get('name')} (id={result.get('id')}). "
            "The expanded search must consider ALL results, not just the first."
        )
