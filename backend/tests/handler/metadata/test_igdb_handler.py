"""Tests for the IGDB metadata handler."""

import json
from collections.abc import AsyncIterator
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import httpx2
import pytest
import pytest_asyncio

import config
from adapters.services.igdb import (
    IGDB_PLATFORM_FAMILIES,
    IGDB_PLATFORM_LIST,
    IGDB_SIBLING_PLATFORMS,
    IGDBService,
)
from adapters.services.igdb_types import (
    AlternativeName,
    ExpandableField,
    Game,
    GameLocalization,
    GameType,
)
from handler.metadata import igdb_handler
from handler.metadata.base_handler import PS1_SERIAL_INDEX_KEY
from handler.metadata.igdb_handler import (
    FAMICOM_IGDB_ID,
    NES_IGDB_ID,
    PS1_IGDB_ID,
    SNES_IGDB_ID,
    SUPER_FAMICOM_IGDB_ID,
    IGDBHandler,
    IGDBMetadata,
    IGDBMetadataMultiplayerMode,
    IGDBMetadataPlatform,
    TwitchAuth,
    _build_platforms_where,
    _platform_igdb_ids_with_twin,
    build_igdb_rom,
    derive_player_count,
    extract_localized_data,
    extract_metadata_from_igdb_rom,
    get_igdb_preferred_locale,
)
from handler.redis_handler import as_text, async_cache
from utils.context import ctx_httpx_client
from utils.platform_slugs import UniversalPlatformSlug as UPS

GENESIS_IGDB_ID = 29


def _make_game(
    game_id: int,
    name: str,
    alternative_names: list[str] | None = None,
    game_localizations: list[str] | None = None,
) -> Game:
    """Build a minimal IGDB Game for testing.

    ``alternative_names`` and ``game_localizations`` accept plain title strings
    and are wrapped into the ``{"name": ...}`` shape IGDB returns.
    """
    alt_names: list[ExpandableField[AlternativeName]] = [
        AlternativeName(id=i, name=n)
        for i, n in enumerate(alternative_names or [], start=1)
    ]
    localizations: list[ExpandableField[GameLocalization]] = [
        GameLocalization(id=i, name=n)
        for i, n in enumerate(game_localizations or [], start=1)
    ]
    return {
        "id": game_id,
        "name": name,
        "slug": name.lower().replace(" ", "-"),
        "summary": "",
        "total_rating": 0.0,
        "aggregated_rating": 0.0,
        "artworks": [],
        "screenshots": [],
        "platforms": [{"id": GENESIS_IGDB_ID, "name": "Sega Mega Drive/Genesis"}],
        "alternative_names": alt_names,
        "genres": [],
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
        "game_localizations": localizations,
    }


class TestGetPlatformAliases:
    @pytest.fixture
    def named_atari_st(self) -> Any:
        entry = {
            **IGDB_PLATFORM_LIST[UPS.ATARI_ST],
            "abbreviation": "ST",
            "alternative_name": "Atari ST/STE",
        }
        with patch.dict(IGDB_PLATFORM_LIST, {UPS.ATARI_ST: entry}):
            yield

    @pytest.mark.usefixtures("named_atari_st")
    def test_platform_carries_abbreviation_and_alternative_name(self) -> None:
        assert IGDBHandler().get_platform_aliases(UPS.ATARI_ST) == (
            "ST",
            ["Atari ST/STE"],
        )

    @pytest.mark.usefixtures("named_atari_st")
    def test_platform_version_shares_main_platform_aliases(self) -> None:
        assert IGDBHandler().get_platform_aliases("520-st") == ("ST", ["Atari ST/STE"])

    def test_comma_separated_alternative_name_splits(self) -> None:
        entry = {
            **IGDB_PLATFORM_LIST[UPS.PSX],
            "abbreviation": "PS1",
            "alternative_name": "PSX, PSOne,  PS ,",
        }
        with patch.dict(IGDB_PLATFORM_LIST, {UPS.PSX: entry}):
            assert IGDBHandler().get_platform_aliases(UPS.PSX) == (
                "PS1",
                ["PSX", "PSOne", "PS"],
            )

    def test_platform_without_aliases(self) -> None:
        entry = IGDB_PLATFORM_LIST[UPS.ATARI_ST].copy()
        entry.pop("abbreviation", None)
        entry.pop("alternative_name", None)
        with patch.dict(IGDB_PLATFORM_LIST, {UPS.ATARI_ST: entry}):
            assert IGDBHandler().get_platform_aliases(UPS.ATARI_ST) == ("", [])


class TestGetIGDBPreferredLocale:
    def test_multi_region_rom_respects_user_priority(self):
        """The configured priority wins over filename tag order."""
        rom = MagicMock()
        rom.regions = ["Japan", "USA"]
        config = MagicMock(SCAN_REGION_PRIORITY=["JP", "us"])

        with patch("handler.metadata.igdb_handler.cm.get_config", return_value=config):
            locale = get_igdb_preferred_locale(rom)

        assert locale == "ja-JP"


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
                # Primary search pass: return no results so we fall through to
                # the expanded search
                return []
            if where and where.startswith("("):
                # Expanded game details lookup: return both candidates
                return [ecco_dolphin, ecco_tides]
            return []

        # Expanded search returns two results: wrong game FIRST, correct game second
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


class TestSonySerialFilenames:
    """Tests for Sony serial resolution in get_rom."""

    @pytest.mark.asyncio
    async def test_serial_at_filename_start_resolves_title(self):
        """A serial in the first two characters of the filename must still hit
        the serial index. Regression: re.IGNORECASE was passed as the ``pos``
        argument of ``Pattern.search()``, skipping the first two characters,
        so files named by their serial (e.g. ``SCUS-94163.bin``) were never
        resolved."""
        handler = IGDBHandler()

        with (
            patch(
                "handler.metadata.igdb_handler.IGDBHandler.is_enabled",
                return_value=True,
            ),
            patch.object(async_cache, "hget", new_callable=AsyncMock) as mock_hget,
            patch.object(
                IGDBHandler, "_search_rom", new_callable=AsyncMock, return_value=None
            ),
        ):
            mock_hget.return_value = json.dumps({"title": "Gran Turismo"})
            result = await handler.get_rom(MagicMock(), "SCUS-94163.bin", PS1_IGDB_ID)

        mock_hget.assert_awaited_once_with(PS1_SERIAL_INDEX_KEY, "SCUS-94163")
        assert result.get("name") == "Gran Turismo"
        assert result["igdb_id"] is None


class TestIsPrefixSupersetMatch:
    """Unit tests for the prefix/superset title heuristic (issue #3805)."""

    @pytest.mark.parametrize(
        ("search_term", "candidate", "expected"),
        [
            # A more specific variant's search term extends the base title.
            (
                "metal gear solid portable ops plus",
                "Metal Gear Solid: Portable Ops",
                True,
            ),
            # Reversed: the base term is a prefix of the variant candidate.
            (
                "Metal Gear Solid: Portable Ops",
                "Metal Gear Solid: Portable Ops Plus",
                True,
            ),
            ("pokemon ranger shadows of almia", "Pokemon Ranger", True),
            # Extra word is not a trailing suffix, so not a prefix relationship.
            ("sonic hedgehog", "Sonic the Hedgehog", False),
            # Identical titles are an exact match, not a prefix ambiguity.
            ("Metal Gear Solid", "metal gear solid", False),
            # Unrelated titles.
            ("contra", "Probotector", False),
        ],
    )
    def test_prefix_superset_detection(self, search_term, candidate, expected):
        handler = IGDBHandler()
        assert handler._is_prefix_superset_match(search_term, candidate) is expected


class TestSearchRomPrefixSupersetVariant:
    """A base title that is a prefix of the searched variant must not be
    accepted when the more specific variant exists (issue #3805).

    'Metal Gear Solid - Portable Ops Plus' and 'Portable Ops' (and the Pokemon
    Ranger series) scored the same IGDB id because the first search pass only
    returned the base game and its ~0.99 Jaro-Winkler score cleared the match
    threshold.
    """

    BASE_ID = 1001
    VARIANT_ID = 1002
    BASE_NAME = "Metal Gear Solid: Portable Ops"
    VARIANT_NAME = "Metal Gear Solid: Portable Ops Plus"

    @pytest.mark.asyncio
    async def test_variant_excluded_by_game_type_is_recovered(self):
        """When the game_type filter hides the variant (IGDB classifies it as an
        expansion), dropping the filter must surface it so the exact match wins
        over the base near-miss."""
        handler = IGDBHandler()

        base = _make_game(self.BASE_ID, self.BASE_NAME)
        variant = _make_game(self.VARIANT_ID, self.VARIANT_NAME)

        async def mock_list_games(
            search_term=None, fields=None, where=None, limit=None
        ):
            # game_type-filtered pass excludes the variant (an expansion type).
            if where and "game_type" in where:
                return [base]
            # Re-query without the game_type filter surfaces both.
            return [base, variant]

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
                "metal gear solid portable ops plus",
                GENESIS_IGDB_ID,
                with_game_type=True,
            )

        assert result is not None
        assert result["id"] == self.VARIANT_ID, (
            f"Expected the '{self.VARIANT_NAME}' variant (id={self.VARIANT_ID}), "
            f"got {result.get('name')} (id={result.get('id')}). The base title is "
            "only a prefix near-miss and must not win over the exact variant."
        )

    @pytest.mark.asyncio
    async def test_base_title_still_matches_when_it_is_the_target(self):
        """Scanning the base game itself must return the base on the first pass
        without any widening (exact match short-circuits)."""
        handler = IGDBHandler()

        base = _make_game(self.BASE_ID, self.BASE_NAME)
        variant = _make_game(self.VARIANT_ID, self.VARIANT_NAME)

        search_mock = AsyncMock(return_value=[])

        async def mock_list_games(
            search_term=None, fields=None, where=None, limit=None
        ):
            # First pass includes both; the base is an exact match.
            if where and "game_type" in where:
                return [base, variant]
            raise AssertionError("widening should not run for an exact match")

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
            patch.object(handler.igdb_service, "search", search_mock),
        ):
            result = await handler._search_rom(
                "metal gear solid portable ops",
                GENESIS_IGDB_ID,
                with_game_type=True,
            )

        assert result is not None
        assert result["id"] == self.BASE_ID
        search_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_prefix_fuzzy_match_does_not_widen(self):
        """A benign non-exact match that is not a prefix/superset must be
        returned from the first pass without extra queries."""
        handler = IGDBHandler()

        game = _make_game(42, "Sonic the Hedgehog")
        search_mock = AsyncMock(return_value=[])

        async def mock_list_games(
            search_term=None, fields=None, where=None, limit=None
        ):
            if where and "game_type" in where:
                return [game]
            raise AssertionError("widening should not run for a non-prefix match")

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
            patch.object(handler.igdb_service, "search", search_mock),
        ):
            result = await handler._search_rom(
                "sonic hedgehog", GENESIS_IGDB_ID, with_game_type=True
            )

        assert result is not None
        assert result["id"] == 42
        search_mock.assert_not_awaited()


def _extract_metadata(**overrides: Any) -> IGDBMetadata:
    """Run the extractor over a minimal game with the given fields overridden."""
    game = _make_game(1, "Test Game")
    game.update(cast("Game", overrides))
    return extract_metadata_from_igdb_rom(IGDBHandler(), game, GENESIS_IGDB_ID)


class TestFranchiseDeduplication:
    """IGDB sends the main franchise both on its own and inside `franchises`.

    Measured on a 14,952-game library: 1,080 of 8,788 games carrying a
    franchise carried it twice (12.3%), reaching the details page as
    "Happy Feet, Happy Feet".
    """

    def test_the_main_franchise_is_not_repeated_inside_the_list(self):
        metadata = _extract_metadata(
            franchise={"name": "Happy Feet"},
            franchises=[{"name": "Happy Feet"}, {"name": "Mumble"}],
        )

        assert metadata["franchises"] == ["Happy Feet", "Mumble"]

    def test_the_main_franchise_stays_first(self):
        """`gamelist` exports `franchises[0]` as <family>, so order matters."""
        metadata = _extract_metadata(
            franchise={"name": "Metroid"},
            franchises=[{"name": "Metroid"}, {"name": "Super Metroid"}],
        )

        assert metadata["franchises"][0] == "Metroid"

    def test_distinct_franchises_are_both_kept(self):
        metadata = _extract_metadata(
            franchise={"name": "Madden"},
            franchises=[{"name": "NFL"}],
        )

        assert metadata["franchises"] == ["Madden", "NFL"]


class TestCompanyRoleDeduplication:
    """`involved_companies` carries one entry per involvement, not per company.

    A studio credited as both developer and publisher therefore appears twice
    in its role list. Measured on a 14,952-game library: 235 developer lists
    and 131 publisher lists repeated a name.
    """

    def test_a_studio_credited_twice_in_one_role_is_listed_once(self):
        involved = [
            {"company": {"name": "Cavia"}, "developer": True, "publisher": False},
            {"company": {"name": "Cavia"}, "developer": True, "publisher": False},
        ]

        assert _extract_metadata(involved_companies=involved)["developers"] == ["Cavia"]

    def test_a_studio_that_both_made_and_shipped_a_game_holds_both_roles(self):
        """The two lists legitimately overlap; neither may repeat internally."""
        involved = [
            {"company": {"name": "Nintendo"}, "developer": True, "publisher": True},
        ]

        metadata = _extract_metadata(involved_companies=involved)

        assert metadata["developers"] == ["Nintendo"]
        assert metadata["publishers"] == ["Nintendo"]

    def test_distinct_developers_keep_their_order(self):
        involved = [
            {"company": {"name": "Crystal Dynamics"}, "developer": True},
            {"company": {"name": "Nixxes Software"}, "developer": True},
        ]

        assert _extract_metadata(involved_companies=involved)["developers"] == [
            "Crystal Dynamics",
            "Nixxes Software",
        ]


TOKEN_KEY = "romm:twitch_token"


class FakeTwitch:
    """Answers Twitch's client-credentials endpoint through a real httpx2 client."""

    def __init__(self) -> None:
        self.requests: list[httpx2.Request] = []
        self.status = 200
        self.body: dict[str, Any] | bytes = {
            "access_token": "fresh-token",
            "expires_in": 5_000_000,
        }
        self.error: Exception | None = None

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if self.error:
            raise self.error
        if isinstance(self.body, bytes):
            return httpx2.Response(self.status, content=self.body)
        return httpx2.Response(self.status, json=self.body)


@pytest_asyncio.fixture
async def twitch(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[FakeTwitch]:
    monkeypatch.setattr(igdb_handler, "IS_PYTEST_RUN", False)
    fake = FakeTwitch()
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(fake))
    token = ctx_httpx_client.set(client)
    await async_cache.delete(TOKEN_KEY)
    try:
        yield fake
    finally:
        await async_cache.delete(TOKEN_KEY)
        ctx_httpx_client.reset(token)
        await client.aclose()


class TestTwitchAuth:
    async def test_fetches_and_caches_a_token(self, twitch: FakeTwitch):
        token = await TwitchAuth()._update_twitch_token()

        assert token == "fresh-token"
        [request] = twitch.requests
        assert request.url.params["grant_type"] == "client_credentials"
        assert request.url.params["client_id"] == config.IGDB_CLIENT_ID
        cached = await async_cache.get(TOKEN_KEY)
        assert cached is not None and as_text(cached) == "fresh-token"
        ttl = await async_cache.ttl(TOKEN_KEY)
        assert 5_000_000 - 20 < ttl <= 5_000_000 - 10

    async def test_rejected_credentials_give_no_token(self, twitch: FakeTwitch):
        twitch.status = 400
        twitch.body = {"message": "invalid client"}

        assert await TwitchAuth()._update_twitch_token() == ""
        assert await async_cache.get(TOKEN_KEY) is None

    @pytest.mark.parametrize(
        "body",
        [
            {"expires_in": 100},
            {"access_token": "t", "expires_in": 0},
            {"access_token": "t", "expires_in": None},
            {"access_token": "t", "expires_in": "100"},
            {"access_token": "t", "expires_in": True},
            {"access_token": 7, "expires_in": 100},
        ],
        ids=[
            "no_token",
            "no_lifetime",
            "null_lifetime",
            "text_lifetime",
            "boolean_lifetime",
            "number_token",
        ],
    )
    async def test_an_incomplete_answer_gives_no_token(
        self, twitch: FakeTwitch, body: dict[str, Any]
    ):
        twitch.body = body

        assert await TwitchAuth()._update_twitch_token() == ""
        assert await async_cache.get(TOKEN_KEY) is None

    @pytest.mark.parametrize(
        "error",
        [httpx2.ConnectError("refused"), httpx2.ReadTimeout("slow")],
        ids=["unreachable", "timed_out"],
    )
    async def test_a_failed_request_gives_no_token(
        self, twitch: FakeTwitch, error: Exception
    ):
        twitch.error = error

        assert await TwitchAuth()._update_twitch_token() == ""

    @pytest.mark.parametrize(
        "body",
        [b"<html>maintenance</html>", b"null", b"[]"],
        ids=["not_json", "null", "list"],
    )
    async def test_a_reply_that_is_not_a_json_object_gives_no_token(
        self, twitch: FakeTwitch, body: bytes
    ):
        twitch.body = body

        assert await TwitchAuth()._update_twitch_token() == ""

    async def test_a_short_lived_token_is_used_but_not_cached(self, twitch: FakeTwitch):
        twitch.body = {"access_token": "brief", "expires_in": 5}

        assert await TwitchAuth()._update_twitch_token() == "brief"
        assert await async_cache.get(TOKEN_KEY) is None

    async def test_the_cached_token_is_reused(self, twitch: FakeTwitch):
        await async_cache.set(TOKEN_KEY, "cached-token", ex=60)

        assert as_text(await TwitchAuth().get_oauth_token()) == "cached-token"
        assert twitch.requests == []

    async def test_a_missing_token_is_fetched(self, twitch: FakeTwitch):
        assert await TwitchAuth().get_oauth_token() == "fresh-token"
        assert len(twitch.requests) == 1

    async def test_disabled_sends_nothing(
        self, twitch: FakeTwitch, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(igdb_handler, "IGDB_CLIENT_ID", "")

        assert await TwitchAuth().get_oauth_token() == ""
        assert await TwitchAuth()._update_twitch_token() == ""
        assert twitch.requests == []


class FakeIGDBService(IGDBService):
    """Stands in for IGDBService, recording each query and playing back replies."""

    def __init__(self) -> None:
        super().__init__(twitch_auth=TwitchAuth())
        self.games: list[list[Game]] = []
        self.search_results: list[list[dict[str, Any]]] = []
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.error: Exception | None = None

    async def list_games(self, **query: Any) -> list[Game]:
        self.calls.append(("games", query))
        if self.error:
            raise self.error
        return self.games.pop(0) if self.games else []

    async def search(self, **query: Any) -> list[dict[str, Any]]:
        self.calls.append(("search", query))
        return self.search_results.pop(0) if self.search_results else []


@pytest.fixture
def service(monkeypatch: pytest.MonkeyPatch) -> FakeIGDBService:
    monkeypatch.setattr(IGDBHandler, "is_enabled", classmethod(lambda cls: True))
    return FakeIGDBService()


@pytest.fixture
def handler(service: FakeIGDBService) -> IGDBHandler:
    handler = IGDBHandler()
    handler.igdb_service = service
    return handler


def _rom() -> MagicMock:
    return MagicMock(regions=[])


class TestHeartbeat:
    async def test_a_game_back_is_healthy(
        self, handler: IGDBHandler, service: FakeIGDBService
    ):
        service.games = [[_make_game(1, "Pong")]]

        assert await handler.heartbeat()
        assert service.calls == [("games", {"fields": ["id"], "limit": 1})]

    async def test_no_games_is_down(self, handler: IGDBHandler):
        assert not await handler.heartbeat()

    async def test_an_error_is_down(
        self, handler: IGDBHandler, service: FakeIGDBService
    ):
        service.error = RuntimeError("boom")

        assert not await handler.heartbeat()

    async def test_disabled_sends_nothing(
        self,
        handler: IGDBHandler,
        service: FakeIGDBService,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(IGDBHandler, "is_enabled", classmethod(lambda cls: False))

        assert not await handler.heartbeat()
        assert service.calls == []


class TestGetPlatform:
    def test_a_known_platform(self, handler: IGDBHandler):
        platform = handler.get_platform("snes")

        assert (platform["igdb_id"], platform.get("name")) == (
            SNES_IGDB_ID,
            "Super Nintendo Entertainment System",
        )

    def test_a_platform_version_maps_to_its_platform(self, handler: IGDBHandler):
        platform = handler.get_platform("10")

        assert platform["igdb_id"] == handler.get_platform("android")["igdb_id"]
        assert platform.get("name") == "10"
        assert platform.get("url_logo") == handler.get_platform("android").get(
            "url_logo"
        )

    def test_an_unlisted_platform_takes_its_siblings_family_and_category(
        self, handler: IGDBHandler
    ):
        assert handler.get_platform("win9x") == {
            "igdb_id": None,
            "slug": "win9x",
            "category": "Operating System",
            "family_name": "Microsoft",
            "family_slug": "microsoft",
        }

    def test_an_unlisted_platform_family_overrides_its_siblings(
        self, handler: IGDBHandler
    ):
        assert handler.get_platform("model2") == {
            "igdb_id": None,
            "slug": "model2",
            "category": "Arcade",
            "family_name": "Sega",
            "family_slug": "sega",
        }

    def test_an_unlisted_platform_with_only_a_family(self, handler: IGDBHandler):
        assert handler.get_platform("ti-994a") == {
            "igdb_id": None,
            "slug": "ti-994a",
            "family_name": "Texas Instruments",
            "family_slug": "texas-instruments",
        }

    def test_every_unlisted_platform_mapping_is_consistent(self):
        assert not IGDB_SIBLING_PLATFORMS.keys() & IGDB_PLATFORM_LIST.keys()
        assert not IGDB_PLATFORM_FAMILIES.keys() & IGDB_PLATFORM_LIST.keys()
        assert all(
            family["family_name"] and family["family_slug"]
            for family in IGDB_PLATFORM_FAMILIES.values()
        )

    def test_an_unknown_platform(self, handler: IGDBHandler):
        assert handler.get_platform("not-a-platform") == {
            "igdb_id": None,
            "slug": "not-a-platform",
        }


def _mode(
    *,
    onlinecoop: bool = False,
    offlinemax: int = 0,
    onlinemax: int = 0,
    onlinecoopmax: int = 0,
    platform_igdb_id: int = 0,
) -> IGDBMetadataMultiplayerMode:
    return IGDBMetadataMultiplayerMode(
        campaigncoop=False,
        dropin=False,
        lancoop=False,
        offlinecoop=False,
        offlinecoopmax=0,
        offlinemax=offlinemax,
        onlinecoop=onlinecoop,
        onlinecoopmax=onlinecoopmax,
        onlinemax=onlinemax,
        splitscreen=False,
        splitscreenonline=False,
        platform=IGDBMetadataPlatform(igdb_id=platform_igdb_id, name=""),
    )


class TestDerivePlayerCount:
    def test_no_multiplayer_modes_is_one_player(self):
        assert derive_player_count([]) == "1"

    def test_any_coop_mode_is_at_least_two_players(self):
        assert derive_player_count([_mode(onlinecoop=True)]) == "1-2"

    def test_the_highest_player_count_wins(self):
        modes = [_mode(offlinemax=4, onlinemax=2), _mode(onlinecoopmax=8)]

        assert derive_player_count(modes) == "1-8"

    def test_only_modes_for_the_platform_count(self):
        modes = [
            _mode(platform_igdb_id=19, offlinemax=4),
            _mode(platform_igdb_id=4, offlinemax=2),
        ]

        assert derive_player_count(modes, platform_igdb_id=4) == "1-2"

    def test_no_mode_for_the_platform_is_one_player(self):
        modes = [_mode(platform_igdb_id=19, offlinemax=4)]

        assert derive_player_count(modes, platform_igdb_id=4) == "1"


def _localized_game() -> Game:
    game = _make_game(1, "Pocket Monsters")
    game["cover"] = {"id": 1, "url": "//images.igdb.com/default.jpg"}
    game["game_localizations"] = [
        {"id": 1, "name": "Eu Monsters", "region": {"id": 1, "identifier": "EU"}},
        {
            "id": 2,
            "name": "ポケットモンスター",
            "region": {"id": 2, "identifier": "ja-JP"},
            "cover": {"id": 2, "url": "//images.igdb.com/ja.jpg"},
        },
        {"id": 3, "name": "No Region"},
    ]
    return game


class TestExtractLocalizedData:
    def test_no_locale_keeps_the_default(self):
        assert extract_localized_data(_localized_game(), None) == (
            "Pocket Monsters",
            "//images.igdb.com/default.jpg",
        )

    def test_a_matching_locale_uses_its_name_and_cover(self):
        assert extract_localized_data(_localized_game(), "ja-JP") == (
            "ポケットモンスター",
            "//images.igdb.com/ja.jpg",
        )

    def test_a_locale_without_its_own_cover_keeps_the_default_cover(self):
        assert extract_localized_data(_localized_game(), "EU") == (
            "Eu Monsters",
            "//images.igdb.com/default.jpg",
        )

    def test_an_unknown_locale_keeps_the_default(self):
        assert extract_localized_data(_localized_game(), "ko-KR") == (
            "Pocket Monsters",
            "//images.igdb.com/default.jpg",
        )


class TestGetRom:
    async def test_matches_by_name(
        self, handler: IGDBHandler, service: FakeIGDBService
    ):
        service.games = [[_make_game(7, "Super Metroid")]]

        rom = await handler.get_rom(_rom(), "Super Metroid (USA).sfc", SNES_IGDB_ID)

        assert (rom["igdb_id"], rom.get("name")) == (7, "Super Metroid")
        kind, query = service.calls[0]
        assert kind == "games"
        assert query["search_term"] == "super metroid"
        assert "game_type" in query["where"]

    async def test_an_igdb_tag_in_the_file_name_is_looked_up_by_id(
        self, handler: IGDBHandler, service: FakeIGDBService
    ):
        service.games = [[_make_game(1103, "Super Metroid")]]

        rom = await handler.get_rom(_rom(), "Metroid 3 (igdb-1103).sfc", SNES_IGDB_ID)

        assert rom["igdb_id"] == 1103
        assert [(kind, query.get("where")) for kind, query in service.calls] == [
            ("games", "id=1103")
        ]

    async def test_an_unknown_igdb_tag_falls_back_to_the_name(
        self, handler: IGDBHandler, service: FakeIGDBService
    ):
        service.games = [[], [_make_game(7, "Super Metroid")]]

        rom = await handler.get_rom(
            _rom(), "Super Metroid (igdb-999999).sfc", SNES_IGDB_ID
        )

        assert rom["igdb_id"] == 7
        assert service.calls[0][1]["where"] == "id=999999"

    async def test_nothing_found_is_no_match(self, handler: IGDBHandler):
        rom = await handler.get_rom(_rom(), "Nothing Like It.sfc", SNES_IGDB_ID)

        assert rom == {"igdb_id": None}

    async def test_no_platform_sends_nothing(
        self, handler: IGDBHandler, service: FakeIGDBService
    ):
        assert await handler.get_rom(_rom(), "Super Metroid.sfc", 0) == {
            "igdb_id": None
        }
        assert service.calls == []


class TestGetMatchedRomById:
    async def test_a_known_id(self, handler: IGDBHandler, service: FakeIGDBService):
        service.games = [[_make_game(7, "Super Metroid")]]

        rom = await handler.get_matched_rom_by_id(_rom(), 7)

        assert rom is not None and rom["igdb_id"] == 7

    async def test_an_unknown_id_is_none(self, handler: IGDBHandler):
        assert await handler.get_matched_rom_by_id(_rom(), 7) is None


class TestGetMatchedRomsByName:
    async def test_merges_name_and_alternative_name_results_once_each(
        self, handler: IGDBHandler, service: FakeIGDBService
    ):
        metroid = _make_game(7, "Super Metroid")
        metroid_2 = _make_game(8, "Metroid II")
        service.games = [[metroid], [metroid, metroid_2]]
        service.search_results = [
            [{"id": 90, "game": {"id": 7}}, {"id": 91, "game": {"id": 8}}]
        ]

        roms = await handler.get_matched_roms_by_name(_rom(), "metroid", SNES_IGDB_ID)

        assert [rom["igdb_id"] for rom in roms] == [7, 8]
        assert service.calls[2][1]["where"] == "id=7 | id=8"

    async def test_no_alternative_names_skips_the_second_lookup(
        self, handler: IGDBHandler, service: FakeIGDBService
    ):
        service.games = [[_make_game(7, "Super Metroid")]]

        roms = await handler.get_matched_roms_by_name(_rom(), "metroid", SNES_IGDB_ID)

        assert [rom["igdb_id"] for rom in roms] == [7]
        assert [kind for kind, _ in service.calls] == ["games", "search"]

    async def test_no_platform_sends_nothing(
        self, handler: IGDBHandler, service: FakeIGDBService
    ):
        assert await handler.get_matched_roms_by_name(_rom(), "metroid", None) == []
        assert service.calls == []


class TestAlternativeNames:
    """Every title IGDB knows lands in `alternative_names`, the canonical name too."""

    def test_localization_titles_join_the_alternative_names(self):
        game = _make_game(
            1,
            "Bleach: The 3rd Phantom",
            alternative_names=["Burīchi Za Sādo Fantomu"],
            game_localizations=[
                "ブリーチ ザ・サード・ファントム",
                "Burīchi Za Sādo Fantomu",
            ],
        )

        rom = build_igdb_rom(IGDBHandler(), game, None, GENESIS_IGDB_ID)

        assert rom["name"] == "Bleach: The 3rd Phantom"
        assert rom["igdb_metadata"]["alternative_names"] == [
            "Bleach: The 3rd Phantom",
            "Burīchi Za Sādo Fantomu",
            "ブリーチ ザ・サード・ファントム",
        ]

    def test_a_localized_display_name_keeps_every_title(self):
        game = _make_game(1, "Bleach: The 3rd Phantom")
        game["game_localizations"] = [
            GameLocalization(
                id=1,
                name="ブリーチ ザ・サード・ファントム",
                region={"id": 1, "identifier": "ja-JP"},
            )
        ]

        rom = build_igdb_rom(IGDBHandler(), game, "ja-JP", GENESIS_IGDB_ID)

        assert rom["name"] == "ブリーチ ザ・サード・ファントム"
        assert rom["igdb_metadata"]["alternative_names"] == [
            "Bleach: The 3rd Phantom",
            "ブリーチ ザ・サード・ファントム",
        ]
