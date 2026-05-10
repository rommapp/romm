"""Tests for the ScreenScraper metadata handler."""

from typing import cast
from unittest.mock import MagicMock, patch

from adapters.services.screenscraper_types import SSGame
from config.config_manager import Config, MetadataMediaType
from handler.metadata.ss_handler import (
    extract_media_from_ss_game,
    extract_metadata_from_ss_rom,
    get_preferred_regions,
)


def _make_config(
    region_priority: list[str] | None = None,
    language_priority: list[str] | None = None,
) -> Config:
    """Build a minimal Config object for testing."""
    return Config(
        EXCLUDED_PLATFORMS=[],
        EXCLUDED_SINGLE_EXT=[],
        EXCLUDED_SINGLE_FILES=[],
        EXCLUDED_MULTI_FILES=[],
        EXCLUDED_MULTI_PARTS_EXT=[],
        EXCLUDED_MULTI_PARTS_FILES=[],
        PLATFORMS_BINDING={},
        PLATFORMS_VERSIONS={},
        ROMS_FOLDER_NAME="roms",
        FIRMWARE_FOLDER_NAME="bios",
        SCAN_REGION_PRIORITY=region_priority or [],
        SCAN_LANGUAGE_PRIORITY=language_priority or ["en"],
        SCAN_MEDIA=["box2d", "box3d", "screenshot"],
        GAMELIST_MEDIA_THUMBNAIL=MetadataMediaType.BOX2D,
        GAMELIST_MEDIA_IMAGE=MetadataMediaType.SCREENSHOT,
    )


class TestGetPreferredRegions:
    def test_includes_cus_by_default(self):
        """cus (custom) region should be included even without user config."""
        config = _make_config(region_priority=[])
        with patch("handler.metadata.ss_handler.cm.get_config", return_value=config):
            regions = get_preferred_regions()

        assert "cus" in regions

    def test_user_cus_priority_respected(self):
        """When user places cus early in priority, it should appear before defaults."""
        config = _make_config(region_priority=["cus", "eu"])
        with patch("handler.metadata.ss_handler.cm.get_config", return_value=config):
            regions = get_preferred_regions()

        assert regions.index("cus") < regions.index("us")

    def test_always_ends_with_unk(self):
        """unk (unknown/no-region) should always be the last fallback."""
        config = _make_config(region_priority=[])
        with patch("handler.metadata.ss_handler.cm.get_config", return_value=config):
            regions = get_preferred_regions()

        assert regions[-1] == "unk"

    def test_no_duplicates(self):
        """Region list should not contain duplicate entries."""
        config = _make_config(region_priority=["us", "wor", "eu"])
        with patch("handler.metadata.ss_handler.cm.get_config", return_value=config):
            regions = get_preferred_regions()

        assert len(regions) == len(set(regions))


class TestExtractMediaFromSsGame:
    """Tests for extract_media_from_ss_game."""

    def _make_rom(self) -> MagicMock:
        rom = MagicMock()
        rom.platform_id = 1
        rom.id = 100
        return rom

    def _make_game_with_cus_only(self) -> SSGame:
        """A game that only has box-2D available in the cus (custom) region."""
        return cast(
            SSGame,
            {
                "medias": [
                    {
                        "type": "box-2D",
                        "parent": "jeu",
                        "region": "cus",
                        "url": "https://screenscraper.example.com/box-2D(cus)",
                        "crc": "aabbccdd",
                        "md5": "deadbeef",
                        "sha1": "cafebabe",
                        "size": "12345",
                        "format": "png",
                    }
                ]
            },
        )

    def test_box2d_cus_region_fetched_without_user_config(self):
        """box-2D with region='cus' must be fetched even when user has no explicit cus config."""
        config = _make_config(region_priority=[])
        rom = self._make_rom()
        game = self._make_game_with_cus_only()

        with (
            patch("handler.metadata.ss_handler.cm.get_config", return_value=config),
            patch(
                "handler.metadata.ss_handler.fs_resource_handler.get_media_resources_path",
                return_value="roms/1/100/box2d",
            ),
        ):
            result = extract_media_from_ss_game(rom, game)

        assert result["box2d_url"] is not None
        assert "box-2D(cus)" in result["box2d_url"]

    def test_preferred_region_wins_over_cus(self):
        """A preferred region match should take priority over cus fallback."""
        config = _make_config(region_priority=["us"])
        rom = self._make_rom()
        game = cast(
            SSGame,
            {
                "medias": [
                    {
                        "type": "box-2D",
                        "parent": "jeu",
                        "region": "cus",
                        "url": "https://screenscraper.example.com/box-2D(cus)",
                        "crc": "aabbccdd",
                        "md5": "deadbeef",
                        "sha1": "cafebabe",
                        "size": "12345",
                        "format": "png",
                    },
                    {
                        "type": "box-2D",
                        "parent": "jeu",
                        "region": "us",
                        "url": "https://screenscraper.example.com/box-2D(us)",
                        "crc": "11223344",
                        "md5": "feedface",
                        "sha1": "baadf00d",
                        "size": "67890",
                        "format": "png",
                    },
                ]
            },
        )

        with (
            patch("handler.metadata.ss_handler.cm.get_config", return_value=config),
            patch(
                "handler.metadata.ss_handler.fs_resource_handler.get_media_resources_path",
                return_value="roms/1/100/box2d",
            ),
        ):
            result = extract_media_from_ss_game(rom, game)

        assert result["box2d_url"] is not None
        assert "box-2D(us)" in result["box2d_url"]


class TestExtractMetadataFromSsRom:
    def _make_rom(self) -> MagicMock:
        rom = MagicMock()
        rom.platform_id = 1
        rom.id = 100
        return rom

    def test_genres_follow_language_priority_with_english_fallback(self):
        config = _make_config(language_priority=["de"])
        rom = self._make_rom()
        game = cast(
            SSGame,
            {
                "genres": [
                    {
                        "noms": [
                            {"langue": "fr", "text": "Shoot'em Up"},
                            {"langue": "en", "text": "Shoot'em Up / Vertical"},
                        ]
                    }
                ]
            },
        )

        with (
            patch("handler.metadata.ss_handler.cm.get_config", return_value=config),
            patch(
                "handler.metadata.ss_handler.fs_resource_handler.get_media_resources_path",
                return_value="roms/1/100/media",
            ),
        ):
            result = extract_metadata_from_ss_rom(rom, game)

        assert result["genres"] == ["Shoot'em Up / Vertical"]
