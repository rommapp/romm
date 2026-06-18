"""Tests for the IGDB metadata handler."""

from unittest.mock import AsyncMock, patch

import pytest

from adapters.services.igdb_types import GameType
from handler.metadata.igdb_handler import (
    FAMICOM_IGDB_ID,
    NES_IGDB_ID,
    SNES_IGDB_ID,
    SUPER_FAMICOM_IGDB_ID,
    IGDBHandler,
    _build_platforms_where,
    _platform_igdb_ids_with_twin,
)

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


class TestRegionalTwinPlatformHelpers:
    """Unit tests for the regional-twin platform helpers (issue #3462).

    IGDB files a console and its regional twin (SNES/Super Famicom,
    NES/Famicom) under separate platform ids, so a search must include both to
    match region-exclusive titles.
    """

    def test_twin_pairs_are_bidirectional(self):
        """Each console resolves to its regional twin in both directions."""
        assert _platform_igdb_ids_with_twin(SNES_IGDB_ID) == [
            SNES_IGDB_ID,
            SUPER_FAMICOM_IGDB_ID,
        ]
        assert _platform_igdb_ids_with_twin(SUPER_FAMICOM_IGDB_ID) == [
            SUPER_FAMICOM_IGDB_ID,
            SNES_IGDB_ID,
        ]
        assert _platform_igdb_ids_with_twin(NES_IGDB_ID) == [
            NES_IGDB_ID,
            FAMICOM_IGDB_ID,
        ]
        assert _platform_igdb_ids_with_twin(FAMICOM_IGDB_ID) == [
            FAMICOM_IGDB_ID,
            NES_IGDB_ID,
        ]

    def test_non_twin_platform_has_no_twin(self):
        """A platform without a regional twin resolves to itself only."""
        assert _platform_igdb_ids_with_twin(GENESIS_IGDB_ID) == [GENESIS_IGDB_ID]

    def test_build_where_single_platform_is_unparenthesized(self):
        """A non-twin platform keeps the original single-clause shape."""
        assert (
            _build_platforms_where(GENESIS_IGDB_ID) == f"platforms=[{GENESIS_IGDB_ID}]"
        )
        assert (
            _build_platforms_where(GENESIS_IGDB_ID, field="game.platforms")
            == f"game.platforms=[{GENESIS_IGDB_ID}]"
        )

    def test_build_where_twin_platform_is_an_or_group(self):
        """A twin platform produces a parenthesized OR of both platform ids."""
        assert (
            _build_platforms_where(SNES_IGDB_ID)
            == f"(platforms=[{SNES_IGDB_ID}] | platforms=[{SUPER_FAMICOM_IGDB_ID}])"
        )
        assert (
            _build_platforms_where(NES_IGDB_ID, field="game.platforms")
            == f"(game.platforms=[{NES_IGDB_ID}] | game.platforms=[{FAMICOM_IGDB_ID}])"
        )


class TestSearchRomRegionalTwinPlatforms:
    """Tests that IGDB search includes a platform's regional twin (issue #3462).

    A Japan-only Super Famicom title (e.g. *Rudra no Hihou*) lives only under
    IGDB's Super Famicom platform, so an ``snes`` scan that filtered to the SNES
    platform alone would silently drop it. The search must query both twins.
    """

    @pytest.mark.asyncio
    async def test_snes_search_matches_super_famicom_only_game(self):
        """A Super-Famicom-only game must match when scanned from ``snes``."""
        handler = IGDBHandler()

        # Rudra no Hihou is catalogued under Super Famicom (58) only.
        rudra = _make_game(829, "Rudra no Hihou")
        captured_wheres: list[str] = []

        async def mock_list_games(
            search_term=None, fields=None, where=None, limit=None
        ):
            captured_wheres.append(where or "")
            # IGDB only surfaces the game when the Super Famicom platform is
            # part of the filter.
            if where and f"platforms=[{SUPER_FAMICOM_IGDB_ID}]" in where:
                return [rudra]
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
                "rudra no hihou", SNES_IGDB_ID, with_game_type=True
            )

        assert result is not None
        assert result["id"] == 829, (
            "Expected Rudra no Hihou (id=829) to match from an snes scan via the "
            f"Super Famicom platform; got {result.get('name')} (id={result.get('id')})"
        )
        # The primary platform filter must mention both twins.
        assert any(
            f"platforms=[{SNES_IGDB_ID}]" in w
            and f"platforms=[{SUPER_FAMICOM_IGDB_ID}]" in w
            for w in captured_wheres
        ), f"Expected SNES + Super Famicom in the platform filter, got: {captured_wheres}"

    @pytest.mark.asyncio
    async def test_nes_search_matches_famicom_only_game(self):
        """A Famicom-only game must match when scanned from ``nes``."""
        handler = IGDBHandler()

        famicom_only = _make_game(1234, "Famicom Mukashi Banashi")
        captured_wheres: list[str] = []

        async def mock_list_games(
            search_term=None, fields=None, where=None, limit=None
        ):
            captured_wheres.append(where or "")
            if where and f"platforms=[{FAMICOM_IGDB_ID}]" in where:
                return [famicom_only]
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
                "famicom mukashi banashi", NES_IGDB_ID, with_game_type=True
            )

        assert result is not None
        assert result["id"] == 1234
        assert any(
            f"platforms=[{NES_IGDB_ID}]" in w and f"platforms=[{FAMICOM_IGDB_ID}]" in w
            for w in captured_wheres
        ), f"Expected NES + Famicom in the platform filter, got: {captured_wheres}"

    @pytest.mark.asyncio
    async def test_super_famicom_search_matches_snes_only_game(self):
        """A Western-only SNES game must match when scanned from ``sfam``."""
        handler = IGDBHandler()

        snes_only = _make_game(4321, "EarthBound")
        captured_wheres: list[str] = []

        async def mock_list_games(
            search_term=None, fields=None, where=None, limit=None
        ):
            captured_wheres.append(where or "")
            if where and f"platforms=[{SNES_IGDB_ID}]" in where:
                return [snes_only]
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
                "earthbound", SUPER_FAMICOM_IGDB_ID, with_game_type=True
            )

        assert result is not None
        assert result["id"] == 4321

    @pytest.mark.asyncio
    async def test_non_twin_platform_filter_is_single_platform(self):
        """A platform without a twin must keep querying only its own id."""
        handler = IGDBHandler()

        game = _make_game(1799, "Ecco the Dolphin")
        captured_wheres: list[str] = []

        async def mock_list_games(
            search_term=None, fields=None, where=None, limit=None
        ):
            captured_wheres.append(where or "")
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
                "ecco the dolphin", GENESIS_IGDB_ID, with_game_type=True
            )

        assert result is not None
        assert result["id"] == 1799
        # No twin → no OR group, just the single platform clause.
        assert all(
            " | " not in w for w in captured_wheres
        ), f"Non-twin platform should not OR a twin platform, got: {captured_wheres}"
        assert any(
            f"platforms=[{GENESIS_IGDB_ID}]" in w for w in captured_wheres
        ), captured_wheres
