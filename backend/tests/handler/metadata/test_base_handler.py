import json
import re
from unittest.mock import AsyncMock, patch

import pytest

from handler.metadata.base_handler import (
    LEADING_ARTICLE_PATTERN,
    MAME_XML_KEY,
    MULTIPLE_SPACE_PATTERN,
    NON_WORD_SPACE_PATTERN,
    PS1_SERIAL_INDEX_KEY,
    PS2_OPL_KEY,
    PS2_OPL_REGEX,
    PS2_SERIAL_INDEX_KEY,
    PSP_SERIAL_INDEX_KEY,
    SONY_SERIAL_REGEX,
    SWITCH_PRODUCT_ID_REGEX,
    SWITCH_TITLEDB_REGEX,
    BaseRom,
    MetadataHandler,
    UniversalPlatformSlug,
    _normalize_search_term,
)
from handler.redis_handler import async_cache


class ExampleMetadataHandler(MetadataHandler):
    @classmethod
    def is_enabled(cls) -> bool:
        return True


class TestNormalizeSearchTerm:
    """Test the _normalize_search_term function."""

    def test_basic_normalization(self):
        """Test basic string normalization."""
        result = _normalize_search_term("Test Game")
        assert result == "test game"

    def test_underscore_replacement(self):
        """Test underscore replacement with spaces."""
        result = _normalize_search_term("Test_Game_Name")
        assert result == "test game name"

    def test_remove_leading_articles(self):
        """Test removal of leading articles."""
        assert _normalize_search_term("The Legend of Zelda") == "legend of zelda"
        assert _normalize_search_term("A New Hope") == "new hope"
        assert _normalize_search_term("An Adventure") == "adventure"

    def test_remove_trailing_articles(self):
        """Test removal of trailing articles."""
        assert _normalize_search_term("Game, The") == "game"
        assert _normalize_search_term("Hope, A") == "hope"

    def test_remove_punctuation(self):
        """Test punctuation removal."""
        result = _normalize_search_term("Mario's Adventure: The Game!")
        assert result == "mario s adventure the game"

    def test_normalize_spaces(self):
        """Test space normalization."""
        result = _normalize_search_term("Game   with    multiple     spaces")
        assert result == "game with multiple spaces"

    def test_unicode_normalization(self):
        """Test Unicode character normalization."""
        result = _normalize_search_term("Pokémon")
        assert result == "pokemon"

    def test_preserve_articles_flag(self):
        """Test keeping articles when remove_articles=False."""
        result = _normalize_search_term("The Legend of Zelda", remove_articles=False)
        assert result == "the legend of zelda"

    def test_preserve_punctuation_flag(self):
        """Test keeping punctuation when remove_punctuation=False."""
        result = _normalize_search_term("Mario's Adventure!", remove_punctuation=False)
        assert result == "mario's adventure!"

    def test_empty_string(self):
        """Test empty string input."""
        result = _normalize_search_term("")
        assert result == ""

    def test_whitespace_only(self):
        """Test whitespace-only input."""
        result = _normalize_search_term("   \t\n   ")
        assert result == ""

    def test_caching_behavior(self):
        """Test that results are cached."""
        _normalize_search_term.cache_clear()

        result1 = _normalize_search_term("Test Game")
        cache_info1 = _normalize_search_term.cache_info()

        result2 = _normalize_search_term("Test Game")
        cache_info2 = _normalize_search_term.cache_info()

        assert result1 == result2
        assert cache_info2.hits == cache_info1.hits + 1


class TestMetadataHandlerMethods:
    """Test MetadataHandler instance methods."""

    @pytest.fixture
    def handler(self):
        return ExampleMetadataHandler()

    def test_normalize_cover_url_with_url(self, handler: MetadataHandler):
        """Test URL normalization with valid URL."""
        url = "//images.example.com/cover.jpg"
        result = handler.normalize_cover_url(url)
        assert result == "https://images.example.com/cover.jpg"

    def test_normalize_cover_url_with_https(self, handler: MetadataHandler):
        """Test URL normalization with existing https."""
        url = "https://images.example.com/cover.jpg"
        result = handler.normalize_cover_url(url)
        assert result == "https://images.example.com/cover.jpg"

    def test_normalize_cover_url_empty(self, handler: MetadataHandler):
        """Test URL normalization with empty string."""
        result = handler.normalize_cover_url("")
        assert result == ""

    def test_normalize_search_term_delegates(self, handler: MetadataHandler):
        """Test that normalize_search_term delegates to the cached function."""
        with patch("handler.metadata.base_handler._normalize_search_term") as mock_func:
            mock_func.return_value = "normalized"

            result = handler.normalize_search_term("Test Game", True, False)

            mock_func.assert_called_once_with("Test Game", True, False)
            assert result == "normalized"

    @pytest.mark.asyncio
    async def test_ps2_opl_format_found(self, handler: MetadataHandler):
        """Test PS2 OPL format when serial is found."""
        with patch.object(async_cache, "hget", new_callable=AsyncMock) as mock_hget:
            mock_hget.return_value = json.dumps({"Name": "Test Game Name"})

            match = re.match(PS2_OPL_REGEX, "SLUS_123.45.iso")
            assert match is not None
            result = await handler._ps2_opl_format(match, "original_name")

            mock_hget.assert_called_once_with(PS2_OPL_KEY, "SLUS_123.45")
            assert result == "Test Game Name"

    @pytest.mark.asyncio
    async def test_ps2_opl_format_not_found(self, handler: MetadataHandler):
        """Test PS2 OPL format when serial is not found."""
        with patch.object(async_cache, "hget", new_callable=AsyncMock) as mock_hget:
            mock_hget.return_value = None

            match = re.match(PS2_OPL_REGEX, "SLUS_123.45.iso")
            assert match is not None
            result = await handler._ps2_opl_format(match, "original_name")

            assert result == "original_name"

    @pytest.mark.asyncio
    async def test_sony_serial_format_found(self, handler: MetadataHandler):
        """Test Sony serial format when found."""
        with patch.object(async_cache, "hget", new_callable=AsyncMock) as mock_hget:
            mock_hget.return_value = json.dumps({"title": "Found Game Title"})

            result = await handler._sony_serial_format("test_key", "SLUS-12345")

            mock_hget.assert_called_once_with("test_key", "SLUS-12345")
            assert result == "Found Game Title"

    @pytest.mark.asyncio
    async def test_sony_serial_format_not_found(self, handler: MetadataHandler):
        """Test Sony serial format when not found."""
        with patch.object(async_cache, "hget", new_callable=AsyncMock) as mock_hget:
            mock_hget.return_value = None

            result = await handler._sony_serial_format("test_key", "SLUS-12345")

            assert result is None

    @pytest.mark.asyncio
    async def test_ps1_serial_format(self, handler: MetadataHandler):
        """Test PS1 serial format."""
        with patch.object(
            handler, "_sony_serial_format", new_callable=AsyncMock
        ) as mock_sony:
            mock_sony.return_value = "PS1 Game Title"

            match = re.match(SONY_SERIAL_REGEX, "SLUS-12345")
            assert match is not None
            result = await handler._ps1_serial_format(match, "original")

            mock_sony.assert_called_once_with(PS1_SERIAL_INDEX_KEY, "SLUS-12345")
            assert result == "PS1 Game Title"

    @pytest.mark.asyncio
    async def test_ps1_serial_format_fallback(self, handler: MetadataHandler):
        """Test PS1 serial format fallback to original."""
        with patch.object(
            handler, "_sony_serial_format", new_callable=AsyncMock
        ) as mock_sony:
            mock_sony.return_value = None

            match = re.match(SONY_SERIAL_REGEX, "SLUS-12345")
            assert match is not None
            result = await handler._ps1_serial_format(match, "original")

            assert result == "original"

    @pytest.mark.asyncio
    async def test_ps2_serial_format(self, handler: MetadataHandler):
        """Test PS2 serial format."""
        with patch.object(
            handler, "_sony_serial_format", new_callable=AsyncMock
        ) as mock_sony:
            mock_sony.return_value = "PS2 Game Title"

            match = re.match(SONY_SERIAL_REGEX, "SLUS-12345")
            if match:
                result = await handler._ps2_serial_format(match, "original")

                mock_sony.assert_called_once_with(PS2_SERIAL_INDEX_KEY, "SLUS-12345")
                assert result == "PS2 Game Title"

    @pytest.mark.asyncio
    async def test_psp_serial_format(self, handler: MetadataHandler):
        """Test PSP serial format."""
        with patch.object(
            handler, "_sony_serial_format", new_callable=AsyncMock
        ) as mock_sony:
            mock_sony.return_value = "PSP Game Title"

            match = re.match(SONY_SERIAL_REGEX, "ULUS-12345")
            if match:
                result = await handler._psp_serial_format(match, "original")

                mock_sony.assert_called_once_with(PSP_SERIAL_INDEX_KEY, "ULUS-12345")
                assert result == "PSP Game Title"

    @pytest.mark.asyncio
    async def test_switch_titledb_format_cache_exists(self, handler: MetadataHandler):
        """Test Switch TitleDB format when cache exists."""
        with patch.object(
            async_cache, "exists", new_callable=AsyncMock
        ) as mock_exists, patch.object(
            async_cache, "hget", new_callable=AsyncMock
        ) as mock_hget:

            mock_exists.return_value = True
            mock_hget.return_value = json.dumps(
                {"name": "Switch Game", "publisher": "Nintendo"}
            )

            match = re.match(SWITCH_TITLEDB_REGEX, "70123456789012")
            assert match is not None
            index_name, index_entry = await handler._switch_titledb_format(
                match, "original"
            )

            mock_hget.assert_called_once()
            assert index_name == "Switch Game"
            assert index_entry is not None
            assert index_entry["publisher"] == "Nintendo"

    @pytest.mark.asyncio
    async def test_switch_titledb_format_not_found(self, handler: MetadataHandler):
        """Test Switch TitleDB format when title ID not found."""
        with patch.object(
            async_cache, "exists", new_callable=AsyncMock
        ) as mock_exists, patch.object(
            async_cache, "hget", new_callable=AsyncMock
        ) as mock_hget:

            mock_exists.return_value = True
            mock_hget.return_value = None

            match = re.match(SWITCH_TITLEDB_REGEX, "70123456789012")
            assert match is not None
            result = await handler._switch_titledb_format(match, "original")

            assert result == ("original", None)

    @pytest.mark.asyncio
    async def test_switch_productid_format_found(self, handler: MetadataHandler):
        """Test Switch Product ID format when found."""
        with patch.object(
            async_cache, "exists", new_callable=AsyncMock
        ) as mock_exists, patch.object(
            async_cache, "hget", new_callable=AsyncMock
        ) as mock_hget:
            mock_exists.return_value = True
            mock_hget.return_value = json.dumps({"name": "Product Game"})

            match = re.match(SWITCH_PRODUCT_ID_REGEX, "0100ABC123456789")
            assert match is not None
            result = await handler._switch_productid_format(match, "original")

            # Check that bitmask 0x800 was cleared (ABC -> AB0)
            mock_hget.assert_called_once_with(
                "romm:switch_product_id",  # SWITCH_PRODUCT_ID_KEY
                "0100ABC123456089",
            )
            assert result[0] == "Product Game"

    @pytest.mark.asyncio
    async def test_mame_format_found(self, handler: MetadataHandler):
        """Test MAME format when entry is found."""
        with patch.object(async_cache, "hget", new_callable=AsyncMock) as mock_hget:
            mock_hget.return_value = json.dumps(
                {"description": "Test MAME Game (Version 1.0)"}
            )

            # Mock the fs_rom_handler import from handler.filesystem
            with patch("handler.filesystem.fs_rom_handler") as mock_fs_handler:
                mock_fs_handler.get_file_name_with_no_tags.return_value = (
                    "Test MAME Game"
                )

                result = await handler._mame_format("test_rom")

                mock_hget.assert_called_once_with(MAME_XML_KEY, "test_rom")
                mock_fs_handler.get_file_name_with_no_tags.assert_called_once_with(
                    "Test MAME Game (Version 1.0)"
                )
                assert result == "Test MAME Game"

    @pytest.mark.asyncio
    async def test_mame_format_not_found(self, handler: MetadataHandler):
        """Test MAME format when entry is not found."""
        with patch.object(async_cache, "hget", new_callable=AsyncMock) as mock_hget:
            mock_hget.return_value = None

            result = await handler._mame_format("test_rom")

            assert result == "test_rom"

    def test_mask_sensitive_values_authorization_bearer(self, handler: MetadataHandler):
        """Test masking Bearer token in Authorization header."""
        values = {"Authorization": "Bearer abc123def456ghi789"}
        result = handler._mask_sensitive_values(values)
        assert result["Authorization"] == "Bearer ab***89"

    def test_mask_sensitive_values_client_keys(self, handler: MetadataHandler):
        """Test masking client keys and secrets."""
        values = {
            "Client-ID": "abcdef123456",
            "Client-Secret": "secret123456789",
            "client_id": "client123456",
            "client_secret": "clientsecret123",
            "api_key": "apikey123456789",
        }
        result = handler._mask_sensitive_values(values)

        assert result["Client-ID"] == "ab***56"
        assert result["Client-Secret"] == "se***89"
        assert result["client_id"] == "cl***56"
        assert result["client_secret"] == "cl***23"
        assert result["api_key"] == "ap***89"

    def test_mask_sensitive_values_retroachievements_keys(
        self, handler: MetadataHandler
    ):
        """Test masking RetroAchievements specific keys."""
        values = {
            "ssid": "sessionid123",
            "sspassword": "sessionpass123",
            "devid": "developer123",
            "devpassword": "devpass123",
            "y": "rapikey123",
        }
        result = handler._mask_sensitive_values(values)

        assert result["ssid"] == "se***23"
        assert result["sspassword"] == "se***23"
        assert result["devid"] == "de***23"
        assert result["devpassword"] == "de***23"
        assert result["y"] == "ra***23"

    def test_mask_sensitive_values_preserves_other_keys(self, handler: MetadataHandler):
        """Test that non-sensitive keys are preserved."""
        values = {
            "regular_key": "regular_value",
            "another_key": "another_value",
            "api_key": "sensitive123",
        }
        result = handler._mask_sensitive_values(values)

        assert result["regular_key"] == "regular_value"
        assert result["another_key"] == "another_value"
        assert result["api_key"] == "se***23"

    def test_mask_sensitive_values_short_values(self, handler: MetadataHandler):
        """Test masking of short values."""
        values = {"api_key": "ab"}
        result = handler._mask_sensitive_values(values)
        assert result["api_key"] == "ab***ab"  # Shows first 2 and last 2


class TestRegexPatterns:
    """Test regex patterns used in the metadata handler."""

    def test_switch_titledb_regex(self):
        """Test Switch TitleDB regex pattern."""
        # Valid title IDs (70 followed by exactly 12 digits)
        assert SWITCH_TITLEDB_REGEX.match("70123456789012")
        assert SWITCH_TITLEDB_REGEX.match("70999999999999")

        # Test finding title IDs within filenames (as used in real code)
        assert SWITCH_TITLEDB_REGEX.search("Game [70123456789012].nsp")
        assert SWITCH_TITLEDB_REGEX.search("70999999999999_update.nsp")

        # Invalid title IDs that should not match
        assert not SWITCH_TITLEDB_REGEX.match("60123456789012")  # Wrong prefix
        assert not SWITCH_TITLEDB_REGEX.match("7012345678901")  # Too short
        assert not SWITCH_TITLEDB_REGEX.search(
            "Game [60123456789012].nsp"
        )  # Wrong prefix in filename
        assert not SWITCH_TITLEDB_REGEX.search(
            "Game [7012345678901].nsp"
        )  # Too short in filename

    def test_switch_product_id_regex(self):
        """Test Switch Product ID regex pattern."""
        # Valid product IDs (0100 followed by exactly 12 hex chars)
        assert SWITCH_PRODUCT_ID_REGEX.match("0100ABC123456789")
        assert SWITCH_PRODUCT_ID_REGEX.match("0100123456789ABC")

        # Invalid product IDs
        assert not SWITCH_PRODUCT_ID_REGEX.match("0200ABC123456789")  # Wrong prefix
        assert not SWITCH_PRODUCT_ID_REGEX.match("0100ABC12345678")  # Too short

    def test_ps2_opl_regex(self):
        """Test PS2 OPL regex pattern."""
        # Valid OPL codes
        match = PS2_OPL_REGEX.match("SLUS_123.45.iso")
        assert match and match.group(1) == "SLUS_123.45"

        match = PS2_OPL_REGEX.match("SCES_987.65.bin")
        assert match and match.group(1) == "SCES_987.65"

        # Invalid codes
        assert not PS2_OPL_REGEX.match("SLUS123.45.iso")  # Missing underscore
        assert not PS2_OPL_REGEX.match("SLU_123.45.iso")  # Wrong length

    def test_sony_serial_regex(self):
        """Test Sony serial regex pattern."""
        # Valid serials
        match = SONY_SERIAL_REGEX.match("SLUS-12345")
        assert match and match.group(1) == "SLUS-12345"

        match = SONY_SERIAL_REGEX.match("Game Title [ULUS-98765]")
        assert match and match.group(1) == "ULUS-98765"

        # Invalid serials
        assert not SONY_SERIAL_REGEX.match("SLU-12345")  # Wrong length
        assert not SONY_SERIAL_REGEX.match("SLUS_12345")  # Wrong separator

    def test_article_patterns(self):
        """Test article removal patterns."""
        # Leading articles (should match at start of string - pattern expects lowercase)
        assert LEADING_ARTICLE_PATTERN.match("the game")
        assert LEADING_ARTICLE_PATTERN.match("a game")
        assert LEADING_ARTICLE_PATTERN.match("an adventure")
        assert LEADING_ARTICLE_PATTERN.match("The Game")
        # Should not match when not at start
        assert not LEADING_ARTICLE_PATTERN.match("game the")

    def test_space_patterns(self):
        """Test space normalization patterns."""
        # Non-word space pattern (should find punctuation)
        assert NON_WORD_SPACE_PATTERN.search("Game's Adventure!")
        assert NON_WORD_SPACE_PATTERN.search("Game: The Return")

        # Multiple space pattern (matches any whitespace - used to normalize spaces)
        assert MULTIPLE_SPACE_PATTERN.search("Game   with    spaces")  # Multiple spaces
        assert MULTIPLE_SPACE_PATTERN.search(
            "Game with spaces"
        )  # Single spaces also match
        assert MULTIPLE_SPACE_PATTERN.search("Game\twith\nspaces")  # Tabs and newlines
        assert not MULTIPLE_SPACE_PATTERN.search("Gamewithoutspaces")  # No spaces


class TestUniversalPlatformSlug:
    """Test UniversalPlatformSlug enum."""

    def test_enum_values_are_strings(self):
        """Test that all enum values are strings."""
        for slug in UniversalPlatformSlug:
            assert isinstance(slug.value, str)
            assert slug.value  # Not empty

    def test_specific_platform_slugs(self):
        """Test specific platform slug values."""
        assert UniversalPlatformSlug.N64 == "n64"
        assert UniversalPlatformSlug.PSX == "psx"
        assert UniversalPlatformSlug.PS2 == "ps2"
        assert UniversalPlatformSlug.SWITCH == "switch"
        assert UniversalPlatformSlug.ARCADE == "arcade"

    def test_enum_contains_expected_platforms(self):
        """Test that enum contains major gaming platforms."""
        expected_platforms = [
            "n64",
            "psx",
            "ps2",
            "ps3",
            "ps4",
            "ps5",
            "switch",
            "wii",
            "wiiu",
            "xbox",
            "xbox360",
            "xboxone",
            "nes",
            "snes",
            "gb",
            "gba",
            "nds",
            "3ds",
            "genesis",
            "saturn",
            "dc",
            "arcade",
        ]

        enum_values = [slug.value for slug in UniversalPlatformSlug]
        for platform in expected_platforms:
            assert platform in enum_values


class TestBaseRomTypedDict:
    """Test BaseRom TypedDict structure."""

    def test_baserom_optional_fields(self):
        """Test that BaseRom allows optional fields."""
        # Empty dict should be valid
        rom: BaseRom = {}
        assert isinstance(rom, dict)

        # Partial dict should be valid
        rom = {"name": "Test Game"}
        assert rom["name"] == "Test Game"

        # Full dict should be valid
        rom = {
            "name": "Test Game",
            "summary": "A test game",
            "url_cover": "https://example.com/cover.jpg",
            "url_screenshots": ["https://example.com/shot1.jpg"],
            "url_manual": "https://example.com/manual.pdf",
        }
        assert len(rom) == 5


class TestConstants:
    """Test module constants."""

    def test_redis_keys_format(self):
        """Test that Redis keys follow expected format."""
        expected_prefix = "romm:"

        redis_keys = [
            MAME_XML_KEY,
            PS2_OPL_KEY,
            PS1_SERIAL_INDEX_KEY,
            PS2_SERIAL_INDEX_KEY,
            PSP_SERIAL_INDEX_KEY,
        ]

        for key in redis_keys:
            assert key.startswith(expected_prefix)
            assert len(key) > len(expected_prefix)

    def test_key_uniqueness(self):
        """Test that all Redis keys are unique."""
        keys = [
            MAME_XML_KEY,
            PS2_OPL_KEY,
            PS1_SERIAL_INDEX_KEY,
            PS2_SERIAL_INDEX_KEY,
            PSP_SERIAL_INDEX_KEY,
        ]

        assert len(keys) == len(set(keys))
