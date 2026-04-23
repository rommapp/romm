"""Tests for the ScreenScraper metadata handler."""

from typing import cast
from unittest.mock import MagicMock, patch

from adapters.services.screenscraper_types import SSGame
from config.config_manager import Config, MetadataMediaType
from handler.metadata.ss_handler import (_decode_html_entities, _get_rom_type,
                                         _is_notgame,
                                         extract_media_from_ss_game,
                                         get_preferred_regions)


def _make_config(region_priority: list[str] | None = None) -> Config:
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
        SCAN_LANGUAGE_PRIORITY=["en"],
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


class TestIsNotgame:
    def _game(self, notgame: str = "false", names: list[str] | None = None) -> SSGame:
        return cast(
            SSGame,
            {
                "notgame": notgame,
                "noms": [
                    {"region": "ss", "text": n} for n in (names or ["Clean Game"])
                ],
            },
        )

    def test_notgame_field_true(self):
        assert _is_notgame(self._game(notgame="true")) is True

    def test_notgame_field_false_clean_name(self):
        assert _is_notgame(self._game(notgame="false")) is False

    def test_zzz_notgame_lowercase_name(self):
        assert _is_notgame(self._game(names=["ZZZ(notgame)"])) is True

    def test_zzz_notgame_long_form(self):
        assert (
            _is_notgame(self._game(names=["ZZZ(NOTGAME):Fichier Annexes - Non Jeux"]))
            is True
        )

    def test_zzz_prefix_only_no_match(self):
        assert _is_notgame(self._game(names=["ZZZ Game Title"])) is False

    def test_missing_notgame_field_clean_name(self):
        game = cast(SSGame, {"noms": [{"region": "ss", "text": "Normal Game"}]})
        assert _is_notgame(game) is False


class TestExtractMediaSensitiveKeyStripping:
    def test_media_url_stored_as_is(self):
        config = _make_config()
        rom = MagicMock()
        rom.platform_id = 1
        rom.id = 100
        full_url = "https://screenscraper.fr/img.png?ssid=user&sspassword=pass&devid=dev&devpassword=devpass&other=keep"
        game = cast(
            SSGame,
            {
                "medias": [
                    {
                        "type": "box-2D",
                        "parent": "jeu",
                        "region": "us",
                        "url": full_url,
                        "crc": "",
                        "md5": "",
                        "sha1": "",
                        "size": "0",
                        "format": "png",
                    }
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

        # SS media URLs are stored as-is — all credentials are needed for downloads
        assert result["box2d_url"] == full_url

    def test_clean_url_unchanged(self):
        config = _make_config()
        rom = MagicMock()
        rom.platform_id = 1
        rom.id = 100
        clean_url = "https://screenscraper.fr/img.png?format=png"
        game = cast(
            SSGame,
            {
                "medias": [
                    {
                        "type": "box-2D",
                        "parent": "jeu",
                        "region": "us",
                        "url": clean_url,
                        "crc": "",
                        "md5": "",
                        "sha1": "",
                        "size": "0",
                        "format": "png",
                    }
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

        assert result["box2d_url"] == clean_url


class TestGetRomType:
    def _file(self, ext: str, top_level: bool = True) -> MagicMock:
        f = MagicMock()
        f.file_extension = ext
        f.is_top_level = top_level
        return f

    def test_iso_extension(self):
        assert _get_rom_type(self._file("iso")) == "iso"

    def test_chd_extension(self):
        assert _get_rom_type(self._file("chd")) == "iso"

    def test_rom_extension(self):
        assert _get_rom_type(self._file("nes")) == "rom"

    def test_folder_based_rom(self):
        assert _get_rom_type(self._file("bin", top_level=False)) == "dossier"


class TestDecodeHtmlEntities:
    def test_amp(self):
        assert _decode_html_entities("Sonic &amp; Tails") == "Sonic & Tails"

    def test_hex_amp(self):
        assert _decode_html_entities("A &#x26; B") == "A & B"

    def test_apostrophe(self):
        assert _decode_html_entities("Donkey Kong&#39;s") == "Donkey Kong's"

    def test_nbsp(self):
        assert _decode_html_entities("Hello&nbsp;World") == "Hello World"

    def test_quot(self):
        assert _decode_html_entities("say &quot;hi&quot;") == 'say "hi"'

    def test_copy(self):
        assert _decode_html_entities("&copy; Nintendo") == "© Nintendo"

    def test_plain_string_unchanged(self):
        assert _decode_html_entities("No entities here") == "No entities here"
