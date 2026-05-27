"""Tests for the ScreenScraper metadata handler."""

from typing import cast
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest

from adapters.services.screenscraper_types import SSGame
from config.config_manager import Config, MetadataMediaType
from handler.metadata.ss_handler import (
    SSHandler,
    _get_rom_type,
    _is_notgame,
    add_ss_auth_to_url,
    extract_media_from_ss_game,
    extract_metadata_from_ss_rom,
    get_preferred_regions,
)


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

    def test_multi_region_rom_respects_user_priority(self):
        """For a multi-region ROM, the user's priority order wins among the
        regions the file is tagged as."""
        rom = MagicMock()
        rom.regions = ["Japan", "USA"]
        config = _make_config(region_priority=["us", "eu"])
        with patch("handler.metadata.ss_handler.cm.get_config", return_value=config):
            regions = get_preferred_regions(rom)

        assert regions.index("us") < regions.index("jp")

    def test_multi_region_rom_untagged_priority_does_not_win(self):
        """A region in SCAN_REGION_PRIORITY that the file is NOT tagged as
        should not outrank a region the file IS tagged as."""
        rom = MagicMock()
        rom.regions = ["Japan", "USA"]
        config = _make_config(region_priority=["eu", "us"])
        with patch("handler.metadata.ss_handler.cm.get_config", return_value=config):
            regions = get_preferred_regions(rom)

        assert regions.index("us") < regions.index("eu")
        assert regions.index("jp") < regions.index("eu")

    def test_multi_region_rom_unprioritized_tags_preserve_order(self):
        """Filename regions not in the priority list keep their filename order
        and follow the prioritized ones."""
        rom = MagicMock()
        rom.regions = ["Japan", "Brazil"]
        config = _make_config(region_priority=["us"])
        with patch("handler.metadata.ss_handler.cm.get_config", return_value=config):
            regions = get_preferred_regions(rom)

        assert regions.index("jp") < regions.index("br")


class TestExtractMediaFromSsGame:
    """Tests for extract_media_from_ss_game."""

    def _make_rom(self, regions: list[str] | None = None) -> MagicMock:
        rom = MagicMock()
        rom.platform_id = 1
        rom.id = 100
        rom.regions = regions
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
    def _make_rom(self, regions: list[str] | None = None) -> MagicMock:
        rom = MagicMock()
        rom.platform_id = 1
        rom.id = 100
        rom.regions = regions
        return rom

    def test_release_date_prefers_tagged_region(self):
        config = _make_config(region_priority=[])
        rom = self._make_rom(regions=["Japan", "USA"])
        game = cast(
            SSGame,
            {
                "dates": [
                    {"region": "us", "text": "1990-02-12"},
                    {"region": "jp", "text": "1988-10-23"},
                    {"region": "eu", "text": "1991-08-29"},
                ],
                "medias": [],
            },
        )

        with patch("handler.metadata.ss_handler.cm.get_config", return_value=config):
            metadata = extract_metadata_from_ss_rom(rom, game)

        assert metadata["first_release_date"] == 593568000


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
    def test_media_url_credentials_stripped(self):
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

        # ssid/sspassword must be stripped before storage so user creds don't
        # end up in the DB. Dev creds and other params must be preserved so
        # subsequent media fetches still resolve.
        stored_url = result["box2d_url"]
        assert stored_url is not None
        query = parse_qs(urlparse(stored_url).query)
        assert "ssid" not in query
        assert "sspassword" not in query
        assert query.get("devid") == ["dev"]
        assert query.get("devpassword") == ["devpass"]
        assert query.get("other") == ["keep"]

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


class TestAddSsAuthToUrl:
    """Tests for add_ss_auth_to_url — re-attaches user creds at download time."""

    def test_appends_credentials_when_configured(self):
        """With both user and password set, creds are appended to the URL."""
        url = "https://screenscraper.fr/img.png?systemeid=1&romnom=Game.zip"
        with (
            patch("handler.metadata.ss_handler.SCREENSCRAPER_USER", "user1"),
            patch("handler.metadata.ss_handler.SCREENSCRAPER_PASSWORD", "pw1"),
        ):
            result = add_ss_auth_to_url(url)

        query = parse_qs(urlparse(result).query)
        assert query.get("ssid") == ["user1"]
        assert query.get("sspassword") == ["pw1"]
        # Other params are preserved
        assert query.get("systemeid") == ["1"]
        assert query.get("romnom") == ["Game.zip"]

    def test_no_op_when_user_missing(self):
        """If SCREENSCRAPER_USER is unset, the URL is returned unchanged."""
        url = "https://screenscraper.fr/img.png?systemeid=1"
        with (
            patch("handler.metadata.ss_handler.SCREENSCRAPER_USER", ""),
            patch("handler.metadata.ss_handler.SCREENSCRAPER_PASSWORD", "pw1"),
        ):
            result = add_ss_auth_to_url(url)

        assert result == url

    def test_no_op_when_password_missing(self):
        """If SCREENSCRAPER_PASSWORD is unset, the URL is returned unchanged."""
        url = "https://screenscraper.fr/img.png?systemeid=1"
        with (
            patch("handler.metadata.ss_handler.SCREENSCRAPER_USER", "user1"),
            patch("handler.metadata.ss_handler.SCREENSCRAPER_PASSWORD", ""),
        ):
            result = add_ss_auth_to_url(url)

        assert result == url

    def test_does_not_duplicate_existing_credentials(self):
        """Pre-existing ssid/sspassword on the URL are replaced, not duplicated."""
        url = "https://screenscraper.fr/img.png?ssid=old&sspassword=oldpw&keep=1"
        with (
            patch("handler.metadata.ss_handler.SCREENSCRAPER_USER", "new"),
            patch("handler.metadata.ss_handler.SCREENSCRAPER_PASSWORD", "newpw"),
        ):
            result = add_ss_auth_to_url(url)

        query = parse_qs(urlparse(result).query)
        # Exactly one occurrence of each, with the new values
        assert query.get("ssid") == ["new"]
        assert query.get("sspassword") == ["newpw"]
        assert query.get("keep") == ["1"]

    def test_handles_stripped_url_from_extract_media(self):
        """A URL that's already had ssid/sspassword stripped (the storage form)
        gets credentials re-attached cleanly, with dev creds and other params
        left intact."""
        # Shape mirrors what extract_media_from_ss_game persists
        stripped_url = (
            "https://screenscraper.fr/img.png?devid=dev&devpassword=devpw&other=keep"
        )
        with (
            patch("handler.metadata.ss_handler.SCREENSCRAPER_USER", "user1"),
            patch("handler.metadata.ss_handler.SCREENSCRAPER_PASSWORD", "pw1"),
        ):
            result = add_ss_auth_to_url(stripped_url)

        query = parse_qs(urlparse(result).query)
        assert query.get("ssid") == ["user1"]
        assert query.get("sspassword") == ["pw1"]
        assert query.get("devid") == ["dev"]
        assert query.get("devpassword") == ["devpw"]
        assert query.get("other") == ["keep"]

    def test_rejects_lookalike_and_attacker_hosts(self):
        """Credentials must only be injected when the hostname is exactly
        screenscraper.fr or a subdomain. A substring match would leak creds
        to attacker-controlled domains."""
        hostile_urls = [
            # Suffix attack: hostname ends with attacker-controlled domain
            "https://screenscraper.fr.evil.example/img.png",
            # Substring in path/query of unrelated host
            "https://evil.example/?u=screenscraper.fr",
            "https://evil.example/screenscraper.fr/img.png",
            # Credentials in userinfo pointing at attacker host
            "https://screenscraper.fr@evil.example/img.png",
            # Prefix attack
            "https://notscreenscraper.fr/img.png",
        ]
        with (
            patch("handler.metadata.ss_handler.SCREENSCRAPER_USER", "user1"),
            patch("handler.metadata.ss_handler.SCREENSCRAPER_PASSWORD", "pw1"),
        ):
            for url in hostile_urls:
                result = add_ss_auth_to_url(url)
                assert result == url, f"Credentials leaked to {url!r}"
                assert "ssid" not in parse_qs(urlparse(result).query)
                assert "sspassword" not in parse_qs(urlparse(result).query)

    def test_accepts_screenscraper_subdomains(self):
        """Subdomains of screenscraper.fr (e.g. api.screenscraper.fr) are
        treated as the same trust boundary and receive credentials."""
        urls = [
            "https://screenscraper.fr/img.png",
            "https://api.screenscraper.fr/api2/foo",
            "https://www.screenscraper.fr/img.png",
            "https://SCREENSCRAPER.FR/img.png",  # case-insensitive host
        ]
        with (
            patch("handler.metadata.ss_handler.SCREENSCRAPER_USER", "user1"),
            patch("handler.metadata.ss_handler.SCREENSCRAPER_PASSWORD", "pw1"),
        ):
            for url in urls:
                result = add_ss_auth_to_url(url)
                query = parse_qs(urlparse(result).query)
                assert query.get("ssid") == ["user1"], f"Creds missing on {url!r}"
                assert query.get("sspassword") == ["pw1"], f"Creds missing on {url!r}"

    def test_strip_then_reauth_roundtrip(self):
        """End-to-end: storing media strips user creds; download-time auth
        restores them without leaking creds into intermediate state."""
        config = _make_config()
        rom = MagicMock()
        rom.platform_id = 1
        rom.id = 100
        original_url = (
            "https://screenscraper.fr/img.png"
            "?ssid=scanner-user&sspassword=scanner-pw&systemeid=1"
        )
        game = cast(
            SSGame,
            {
                "medias": [
                    {
                        "type": "box-2D",
                        "parent": "jeu",
                        "region": "us",
                        "url": original_url,
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
            extracted = extract_media_from_ss_game(rom, game)

        stored_url = extracted["box2d_url"]
        assert stored_url is not None

        # Stored URL must not carry user creds
        stored_query = parse_qs(urlparse(stored_url).query)
        assert "ssid" not in stored_query
        assert "sspassword" not in stored_query

        # At download time, add_ss_auth_to_url re-attaches the *current* creds
        with (
            patch("handler.metadata.ss_handler.SCREENSCRAPER_USER", "download-user"),
            patch("handler.metadata.ss_handler.SCREENSCRAPER_PASSWORD", "download-pw"),
        ):
            download_url = add_ss_auth_to_url(stored_url)

        download_query = parse_qs(urlparse(download_url).query)
        assert download_query.get("ssid") == ["download-user"]
        assert download_query.get("sspassword") == ["download-pw"]
        assert download_query.get("systemeid") == ["1"]


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


class TestLookupRom:
    def _make_mock_file(self) -> MagicMock:
        f = MagicMock()
        f.file_size_bytes = 1024
        f.is_top_level = True
        f.file_extension = "bin"
        f.md5_hash = "abc123"
        f.sha1_hash = "def456"
        f.crc_hash = "12345678"
        f.file_name = "bios.bin"
        return f

    @pytest.mark.asyncio
    async def test_returns_notgame_flag_on_notgame_field(self):
        notgame_response = {
            "id": "999",
            "notgame": "true",
            "noms": [{"region": "wor", "text": "SomeBios"}],
        }
        handler = SSHandler()
        with patch.object(
            handler.ss_service, "get_game_info", return_value=notgame_response
        ):
            result, is_not_game = await handler.lookup_rom(
                MagicMock(platform_slug="snes"), 3, [self._make_mock_file()]
            )
        assert result["ss_id"] is None
        assert is_not_game is True

    @pytest.mark.asyncio
    async def test_returns_notgame_flag_on_zzz_prefix(self):
        notgame_response = {
            "id": "0",
            "notgame": "false",
            "noms": [{"region": "wor", "text": "ZZZ(NOTGAME)SomeBios"}],
        }
        handler = SSHandler()
        with patch.object(
            handler.ss_service, "get_game_info", return_value=notgame_response
        ):
            result, is_not_game = await handler.lookup_rom(
                MagicMock(platform_slug="snes"), 3, [self._make_mock_file()]
            )
        assert result["ss_id"] is None
        assert is_not_game is True
