"""Tests for the IGDB metadata handler."""

from unittest.mock import AsyncMock, patch

import pytest

from adapters.services.igdb_types import GameType
from handler.metadata.igdb_handler import IGDBHandler

GENESIS_IGDB_ID = 29


def _make_game(
    game_id: int,
    name: str,
    alternative_names: list[str] | None = None,
    game_localizations: list[str] | None = None,
) -> dict:
    """Build a minimal IGDB Game dict for testing.

    ``alternative_names`` and ``game_localizations`` accept plain title strings
    and are wrapped into the ``{"name": ...}`` shape IGDB returns.
    """
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
        "alternative_names": [{"name": n} for n in (alternative_names or [])],
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
        "game_localizations": [{"name": n} for n in (game_localizations or [])],
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
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await handler._search_rom(
                "ecco the tides of time", GENESIS_IGDB_ID, with_game_type=True
            )

        assert result is not None
        assert (
            result["id"] == 5379
        ), f"Expected Ecco: The Tides of Time (id=5379), got {result.get('name')} (id={result.get('id')})"

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
                new_callable=AsyncMock,
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


class TestSearchRomLocalizedNames:
    """Tests for matching ROMs by localized / alternative titles.

    Regression coverage for issue #3435: a ROM whose No-Intro / ReDump filename
    uses a localized title (e.g. ``007 - Die Welt Ist Nicht Genug (Germany)``)
    must match the IGDB game that lists that title in ``alternative_names`` or
    ``game_localizations``, not only the primary English ``name``.
    """

    # James Bond 007: The World Is Not Enough, IGDB id 158962, has the German
    # alternative name "007 - Die Welt Ist Nicht Genug" (issue #3435).
    ENGLISH_NAME = "James Bond 007: The World Is Not Enough"
    GERMAN_TITLE = "007 - Die Welt Ist Nicht Genug"
    GAME_ID = 158962

    @pytest.mark.asyncio
    async def test_alt_name_match_in_primary_games_search(self):
        """A localized filename must match when IGDB returns the game on the
        primary games-endpoint pass and the term only matches an alternative
        name, not the primary English name."""
        handler = IGDBHandler()

        game = _make_game(
            self.GAME_ID,
            self.ENGLISH_NAME,
            alternative_names=[self.GERMAN_TITLE],
        )

        async def mock_list_games(
            search_term=None, fields=None, where=None, limit=None
        ):
            # Primary games-endpoint pass returns the game (IGDB's fuzzy search
            # surfaces it via the alt name), but the term won't match the
            # English primary name on its own.
            return [game]

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
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await handler._search_rom(
                "007 die welt ist nicht genug", GENESIS_IGDB_ID
            )

        assert result is not None
        assert result["id"] == self.GAME_ID, (
            f"Expected {self.ENGLISH_NAME} (id={self.GAME_ID}) via its German "
            f"alternative name, got {result.get('name')} (id={result.get('id')})"
        )

    @pytest.mark.asyncio
    async def test_alt_name_match_in_expanded_search(self):
        """A localized filename must match when the game is only discovered via
        the expanded ``/search`` alternative_name query and the term matches an
        alternative name rather than the primary English name."""
        handler = IGDBHandler()

        game = _make_game(
            self.GAME_ID,
            self.ENGLISH_NAME,
            alternative_names=[self.GERMAN_TITLE],
        )

        async def mock_list_games(
            search_term=None, fields=None, where=None, limit=None
        ):
            # Expanded game-details lookup (id filter) returns the full game.
            if where and where.startswith("("):
                return [game]
            # Primary pass returns nothing useful.
            return []

        expanded_results = [{"game": {"id": self.GAME_ID}, "name": self.ENGLISH_NAME}]

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
                new_callable=AsyncMock,
                return_value=expanded_results,
            ),
        ):
            result = await handler._search_rom(
                "007 die welt ist nicht genug", GENESIS_IGDB_ID
            )

        assert result is not None
        assert result["id"] == self.GAME_ID, (
            f"Expected {self.ENGLISH_NAME} (id={self.GAME_ID}) via its German "
            f"alternative name, got {result.get('name')} (id={result.get('id')})"
        )

    @pytest.mark.asyncio
    async def test_localization_name_match_in_expanded_search(self):
        """A localized filename must match when the matching title lives in
        ``game_localizations`` rather than ``alternative_names``."""
        handler = IGDBHandler()

        game = _make_game(
            self.GAME_ID,
            self.ENGLISH_NAME,
            game_localizations=[self.GERMAN_TITLE],
        )

        async def mock_list_games(
            search_term=None, fields=None, where=None, limit=None
        ):
            if where and where.startswith("("):
                return [game]
            return []

        expanded_results = [{"game": {"id": self.GAME_ID}, "name": self.ENGLISH_NAME}]

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
                new_callable=AsyncMock,
                return_value=expanded_results,
            ),
        ):
            result = await handler._search_rom(
                "007 die welt ist nicht genug", GENESIS_IGDB_ID
            )

        assert result is not None
        assert result["id"] == self.GAME_ID

    @pytest.mark.asyncio
    async def test_primary_english_name_still_matches(self):
        """Indexing alternative titles must not regress matching by the primary
        English name."""
        handler = IGDBHandler()

        game = _make_game(
            self.GAME_ID,
            self.ENGLISH_NAME,
            alternative_names=[self.GERMAN_TITLE],
        )

        async def mock_list_games(
            search_term=None, fields=None, where=None, limit=None
        ):
            return [game]

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
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await handler._search_rom(
                "james bond 007 the world is not enough", GENESIS_IGDB_ID
            )

        assert result is not None
        assert result["id"] == self.GAME_ID

    @pytest.mark.asyncio
    async def test_primary_name_wins_over_other_games_alt_name(self):
        """When a search term equals one game's primary name and another game's
        alternative name, the primary-name owner must win (alt titles fill in
        only names not already claimed by a primary name)."""
        handler = IGDBHandler()

        primary = _make_game(100, "Contra")
        # A different, higher-id game that lists "Contra" as an alt title.
        other = _make_game(200, "Probotector", alternative_names=["Contra"])

        async def mock_list_games(
            search_term=None, fields=None, where=None, limit=None
        ):
            return [other, primary]

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
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await handler._search_rom("contra", GENESIS_IGDB_ID)

        assert result is not None
        assert result["id"] == 100, (
            "Expected the game whose primary name is 'Contra' (id=100), not the "
            f"game that merely lists it as an alternative name; got id={result.get('id')}"
        )
