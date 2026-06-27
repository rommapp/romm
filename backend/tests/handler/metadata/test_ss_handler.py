"""Tests for the ScreenScraper metadata handler."""

from typing import cast
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest

from adapters.services.screenscraper import SS_DEV_ID, SS_DEV_PASSWORD
from adapters.services.screenscraper_types import SSGame
from config.config_manager import Config, MetadataMediaType
from handler.metadata.ss_handler import (
    SSHandler,
    _get_rom_type,
    _is_notgame,
    _ss_media_descriptor,
    add_ss_auth_to_url,
    build_ss_game,
    extract_media_from_ss_game,
    extract_metadata_from_ss_rom,
    get_preferred_regions,
    is_screenscraper_url,
    pop_ss_media_urls,
)


def _make_config(
    region_priority: list[str] | None = None,
    scan_media: list[str] | None = None,
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
        SCAN_LANGUAGE_PRIORITY=["en"],
        SCAN_MEDIA=(
            scan_media if scan_media is not None else ["box2d", "box3d", "screenshot"]
        ),
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

    def _make_game_with_box_faces(self) -> SSGame:
        """A game exposing all three box faces: front, back and spine."""
        return cast(
            SSGame,
            {
                "medias": [
                    {
                        "type": "box-2D",
                        "parent": "jeu",
                        "region": "us",
                        "url": "https://screenscraper.example.com/box-2D",
                        "crc": "aabbccdd",
                        "md5": "deadbeef",
                        "sha1": "cafebabe",
                        "size": "12345",
                        "format": "png",
                    },
                    {
                        "type": "box-2D-back",
                        "parent": "jeu",
                        "region": "us",
                        "url": "https://screenscraper.example.com/box-2D-back",
                        "crc": "11223344",
                        "md5": "feedface",
                        "sha1": "baadf00d",
                        "size": "23456",
                        "format": "png",
                    },
                    {
                        "type": "box-2D-side",
                        "parent": "jeu",
                        "region": "us",
                        "url": "https://screenscraper.example.com/box-2D-side",
                        "crc": "55667788",
                        "md5": "0ddba11",
                        "sha1": "f00dcafe",
                        "size": "34567",
                        "format": "png",
                    },
                ]
            },
        )

    def test_box2d_side_path_set_when_in_config(self):
        """When 'box2d_side' is in SCAN_MEDIA the spine is persisted locally."""
        config = _make_config(scan_media=["box2d", "box2d_back", "box2d_side"])
        rom = self._make_rom()
        game = self._make_game_with_box_faces()

        with (
            patch("handler.metadata.ss_handler.cm.get_config", return_value=config),
            patch(
                "handler.metadata.ss_handler.fs_resource_handler.get_media_resources_path",
                side_effect=lambda pid, rid, mt: f"roms/{pid}/{rid}/{mt.value}",
            ),
        ):
            result = extract_media_from_ss_game(rom, game)

        assert result["box2d_side_url"] is not None
        assert "box-2D-side" in result["box2d_side_url"]
        assert result["box2d_side_path"] == "roms/1/100/box2d_side/box2d_side.png"

    def test_box2d_side_path_not_set_when_absent_from_config(self):
        """Without 'box2d_side' in SCAN_MEDIA the spine URL is kept but not stored."""
        config = _make_config(scan_media=["box2d", "box2d_back"])
        rom = self._make_rom()
        game = self._make_game_with_box_faces()

        with (
            patch("handler.metadata.ss_handler.cm.get_config", return_value=config),
            patch(
                "handler.metadata.ss_handler.fs_resource_handler.get_media_resources_path",
                side_effect=lambda pid, rid, mt: f"roms/{pid}/{rid}/{mt.value}",
            ),
        ):
            result = extract_media_from_ss_game(rom, game)

        assert result["box2d_side_url"] is not None
        assert result["box2d_side_path"] is None

    def _make_game_with_both_miximage_versions(self) -> SSGame:
        """A game that has both mixrbv1 and mixrbv2 (v1 listed first, matching SS API order)."""
        return cast(
            SSGame,
            {
                "medias": [
                    {
                        "type": "mixrbv1",
                        "parent": "jeu",
                        "region": "us",
                        "url": "https://screenscraper.example.com/mixrbv1",
                        "crc": "aabbccdd",
                        "md5": "deadbeef",
                        "sha1": "cafebabe",
                        "size": "12345",
                        "format": "png",
                    },
                    {
                        "type": "mixrbv2",
                        "parent": "jeu",
                        "region": "us",
                        "url": "https://screenscraper.example.com/mixrbv2",
                        "crc": "11223344",
                        "md5": "feedface",
                        "sha1": "baadf00d",
                        "size": "67890",
                        "format": "png",
                    },
                ]
            },
        )

    def test_miximage_maps_to_mixrbv1(self):
        """When 'miximage' is in SCAN_MEDIA, only mixrbv1 is downloaded."""
        config = _make_config(scan_media=["miximage"])
        rom = self._make_rom()
        game = self._make_game_with_both_miximage_versions()

        with (
            patch("handler.metadata.ss_handler.cm.get_config", return_value=config),
            patch(
                "handler.metadata.ss_handler.fs_resource_handler.get_media_resources_path",
                return_value="roms/1/100/miximage",
            ),
        ):
            result = extract_media_from_ss_game(rom, game)

        assert result["miximage_url"] is not None
        assert "mixrbv1" in result["miximage_url"]
        assert result["miximage_path"] is not None
        assert result["miximage_v2_url"] is not None
        assert "mixrbv2" in result["miximage_v2_url"]
        assert result["miximage_v2_path"] is None

    def test_miximage_v2_maps_to_mixrbv2(self):
        """When 'miximage_v2' is in SCAN_MEDIA, only mixrbv2 is downloaded."""
        config = _make_config(scan_media=["miximage_v2"])
        rom = self._make_rom()
        game = self._make_game_with_both_miximage_versions()

        with (
            patch("handler.metadata.ss_handler.cm.get_config", return_value=config),
            patch(
                "handler.metadata.ss_handler.fs_resource_handler.get_media_resources_path",
                return_value="roms/1/100/miximage_v2",
            ),
        ):
            result = extract_media_from_ss_game(rom, game)

        assert result["miximage_v2_url"] is not None
        assert "mixrbv2" in result["miximage_v2_url"]
        assert result["miximage_v2_path"] is not None
        assert result["miximage_url"] is not None
        assert "mixrbv1" in result["miximage_url"]
        assert result["miximage_path"] is None

    def test_miximage_v2_not_downloaded_when_only_miximage_in_config(self):
        """When only 'miximage' is in SCAN_MEDIA, miximage_v2_path is not set."""
        config = _make_config(scan_media=["miximage"])
        rom = self._make_rom()
        game = self._make_game_with_both_miximage_versions()

        with (
            patch("handler.metadata.ss_handler.cm.get_config", return_value=config),
            patch(
                "handler.metadata.ss_handler.fs_resource_handler.get_media_resources_path",
                return_value="roms/1/100/miximage",
            ),
        ):
            result = extract_media_from_ss_game(rom, game)

        assert result["miximage_v2_path"] is None

    def test_miximage_v1_not_downloaded_when_only_miximage_v2_in_config(self):
        """When only 'miximage_v2' is in SCAN_MEDIA, miximage_path is not set."""
        config = _make_config(scan_media=["miximage_v2"])
        rom = self._make_rom()
        game = self._make_game_with_both_miximage_versions()

        with (
            patch("handler.metadata.ss_handler.cm.get_config", return_value=config),
            patch(
                "handler.metadata.ss_handler.fs_resource_handler.get_media_resources_path",
                return_value="roms/1/100/miximage_v2",
            ),
        ):
            result = extract_media_from_ss_game(rom, game)

        assert result["miximage_path"] is None

    def test_both_miximage_versions_downloaded_when_both_in_config(self):
        """When both 'miximage' and 'miximage_v2' are in SCAN_MEDIA, both are downloaded."""
        config = _make_config(scan_media=["miximage", "miximage_v2"])
        rom = self._make_rom()
        game = self._make_game_with_both_miximage_versions()

        with (
            patch("handler.metadata.ss_handler.cm.get_config", return_value=config),
            patch(
                "handler.metadata.ss_handler.fs_resource_handler.get_media_resources_path",
                side_effect=lambda pid, rid, mt: f"roms/{pid}/{rid}/{mt.value}",
            ),
        ):
            result = extract_media_from_ss_game(rom, game)

        assert result["miximage_url"] is not None
        assert "mixrbv1" in result["miximage_url"]
        assert result["miximage_path"] is not None
        assert result["miximage_v2_url"] is not None
        assert "mixrbv2" in result["miximage_v2_url"]
        assert result["miximage_v2_path"] is not None


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

        # All SS auth params (user creds AND dev creds) must be stripped before
        # storage so no authentication detail ends up in the DB (issue #3612).
        # Non-auth params are preserved so the change-check and re-auth download
        # still resolve.
        stored_url = result["box2d_url"]
        assert stored_url is not None
        query = parse_qs(urlparse(stored_url).query)
        assert "ssid" not in query
        assert "sspassword" not in query
        assert "devid" not in query
        assert "devpassword" not in query
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
        """A URL that's had all SS auth params stripped (the storage form) gets
        the full credential set (user creds AND dev creds) re-attached cleanly,
        with non-auth params left intact."""
        # Shape mirrors what extract_media_from_ss_game persists: no auth params,
        # only the functional ones needed to resolve the media.
        stripped_url = "https://screenscraper.fr/img.png?systemeid=1&other=keep"
        with (
            patch("handler.metadata.ss_handler.SCREENSCRAPER_USER", "user1"),
            patch("handler.metadata.ss_handler.SCREENSCRAPER_PASSWORD", "pw1"),
        ):
            result = add_ss_auth_to_url(stripped_url)

        query = parse_qs(urlparse(result).query)
        assert query.get("ssid") == ["user1"]
        assert query.get("sspassword") == ["pw1"]
        assert query.get("devid") == [SS_DEV_ID]
        assert query.get("devpassword") == [SS_DEV_PASSWORD]
        assert query.get("systemeid") == ["1"]
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
        assert download_query.get("devid") == [SS_DEV_ID]
        assert download_query.get("devpassword") == [SS_DEV_PASSWORD]
        assert download_query.get("systemeid") == ["1"]

    def test_appends_dev_credentials_when_configured(self):
        """Dev creds are re-attached alongside user creds, since they are now
        stripped from stored URLs and required for SS media downloads."""
        url = "https://screenscraper.fr/img.png?systemeid=1"
        with (
            patch("handler.metadata.ss_handler.SCREENSCRAPER_USER", "user1"),
            patch("handler.metadata.ss_handler.SCREENSCRAPER_PASSWORD", "pw1"),
        ):
            result = add_ss_auth_to_url(url)

        query = parse_qs(urlparse(result).query)
        assert query.get("devid") == [SS_DEV_ID]
        assert query.get("devpassword") == [SS_DEV_PASSWORD]
        assert query.get("ssid") == ["user1"]
        assert query.get("sspassword") == ["pw1"]


class TestPopSsMediaUrls:
    """Tests for pop_ss_media_urls: removes the never-persisted media URLs."""

    def test_removes_all_url_fields_and_returns_them(self):
        ss_metadata = {
            "box2d_url": "https://screenscraper.fr/box.png?systemeid=1",
            "box2d_path": "roms/1/100/box2d.png",
            "screenshot_url": "https://screenscraper.fr/ss.png?systemeid=1",
            "video_normalized_url": "https://screenscraper.fr/v.mp4",
            "ss_score": "8.0",
            "genres": ["Action"],
        }

        popped = pop_ss_media_urls(ss_metadata)

        # Every *_url key is removed from the dict in place
        assert all(not key.endswith("_url") for key in ss_metadata)
        # Non-URL data (paths, scalar metadata) is left untouched
        assert ss_metadata["box2d_path"] == "roms/1/100/box2d.png"
        assert ss_metadata["ss_score"] == "8.0"
        assert ss_metadata["genres"] == ["Action"]
        # The removed URLs are returned so the caller can drive the download
        assert popped == {
            "box2d_url": "https://screenscraper.fr/box.png?systemeid=1",
            "screenshot_url": "https://screenscraper.fr/ss.png?systemeid=1",
            "video_normalized_url": "https://screenscraper.fr/v.mp4",
        }

    def test_no_url_fields_is_noop(self):
        ss_metadata = {"box2d_path": "roms/1/100/box2d.png", "ss_score": "8.0"}

        popped = pop_ss_media_urls(ss_metadata)

        assert popped == {}
        assert ss_metadata == {"box2d_path": "roms/1/100/box2d.png", "ss_score": "8.0"}

    def test_empty_dict(self):
        assert pop_ss_media_urls({}) == {}


class TestIsScreenscraperUrl:
    def test_host_and_subdomain(self):
        assert is_screenscraper_url("https://screenscraper.fr/img.png")
        assert is_screenscraper_url("https://api.screenscraper.fr/api2/mediaJeu.php")

    def test_non_ss_and_lookalike(self):
        assert not is_screenscraper_url("https://images.igdb.com/co1.jpg")
        assert not is_screenscraper_url("https://screenscraper.fr.evil.example/x.png")

    def test_empty_and_none(self):
        assert not is_screenscraper_url("")
        assert not is_screenscraper_url(None)


class TestSsMediaDescriptor:
    """Tests for _ss_media_descriptor: the non-sensitive change-detection tag."""

    def test_extracts_media_param(self):
        url = (
            "https://api.screenscraper.fr/api2/mediaJeu.php"
            "?systemeid=1&jeuid=2&media=box-2D(wor)"
        )
        assert _ss_media_descriptor(url) == "box-2D(wor)"

    def test_region_change_yields_different_tag(self):
        wor = "https://api.screenscraper.fr/api2/mediaJeu.php?jeuid=2&media=box-2D(wor)"
        jp = "https://api.screenscraper.fr/api2/mediaJeu.php?jeuid=2&media=box-2D(jp)"
        assert _ss_media_descriptor(wor) != _ss_media_descriptor(jp)

    def test_no_media_param(self):
        assert _ss_media_descriptor("https://screenscraper.fr/img.png") is None

    def test_none(self):
        assert _ss_media_descriptor(None) is None


class TestBuildSsGameTags:
    """build_ss_game must persist variant tags (not URLs) for change detection."""

    def _game(self) -> SSGame:
        base = "https://api.screenscraper.fr/api2/mediaJeu.php?systemeid=1&jeuid=42"
        return cast(
            SSGame,
            {
                "id": "42",
                "noms": [{"region": "us", "text": "Test Game"}],
                "medias": [
                    {
                        "type": "box-2D",
                        "parent": "jeu",
                        "region": "us",
                        "url": f"{base}&media=box-2D(us)",
                        "crc": "",
                        "md5": "",
                        "sha1": "",
                        "size": "0",
                        "format": "png",
                    },
                    {
                        "type": "ss",
                        "parent": "jeu",
                        "region": "us",
                        "url": f"{base}&media=ss(us)",
                        "crc": "",
                        "md5": "",
                        "sha1": "",
                        "size": "0",
                        "format": "png",
                    },
                ],
            },
        )

    def test_tags_populated_from_resolved_media(self):
        config = _make_config(
            region_priority=["us"], scan_media=["box2d", "screenshot"]
        )
        rom = MagicMock()
        rom.platform_id = 1
        rom.id = 100
        rom.regions = ["USA"]

        with (
            patch("handler.metadata.ss_handler.cm.get_config", return_value=config),
            patch(
                "handler.metadata.ss_handler.fs_resource_handler.get_media_resources_path",
                return_value="roms/1/100/m",
            ),
        ):
            result = build_ss_game(rom, self._game())

        ss_metadata = result["ss_metadata"]
        # The variant tags are derived from the resolved media. They (not the
        # URLs) are what survives persistence; pop_ss_media_urls removes the
        # in-memory *_url fields at the persist boundary.
        assert ss_metadata["cover_media"] == "box-2D(us)"
        assert ss_metadata["screenshot_media"] == ["ss(us)"]
        surviving = {k: v for k, v in ss_metadata.items() if not k.endswith("_url")}
        assert surviving["cover_media"] == "box-2D(us)"


class TestGetPlatform:
    """Tests for SSHandler.get_platform — the slug → ScreenScraper system map."""

    def test_unmapped_platform_returns_none_ss_id(self):
        """A slug with no ScreenScraper mapping yields ss_id=None (lookup skipped)."""
        handler = SSHandler()
        platform = handler.get_platform("not-a-real-platform")

        assert platform["ss_id"] is None
        assert platform["slug"] == "not-a-real-platform"


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

    def _make_unhashed_file(
        self, file_name: str = "Adventure Island II (USA).nes"
    ) -> MagicMock:
        """A top-level file with no hashes, as produced for NON_HASHABLE_PLATFORMS
        or when SKIP_HASH_CALCULATION is enabled."""
        f = MagicMock()
        f.file_size_bytes = 131072
        f.is_top_level = True
        f.file_extension = "nes"
        f.md5_hash = ""
        f.sha1_hash = ""
        f.crc_hash = ""
        f.file_name = file_name
        f.archive_members = None
        return f

    @pytest.mark.asyncio
    async def test_no_hash_still_attempts_jeuinfos_by_filename(self):
        """A file with no hashes must still reach jeuInfos using the filename
        (romnom) + platform (systemeid), instead of bailing out and degrading to
        the weaker jeuRecherche name search."""
        handler = SSHandler()
        mock_file = self._make_unhashed_file("Adventure Island II (USA).nes")
        captured = {}

        async def capture(**kwargs):
            captured.update(kwargs)
            return None

        with patch.object(handler.ss_service, "get_game_info", side_effect=capture):
            result, is_not_game = await handler.lookup_rom(
                MagicMock(platform_slug="nes"), 3, [mock_file]
            )

        assert captured, "get_game_info should be called even without hashes"
        assert captured.get("rom_name") == "Adventure Island II (USA).nes"
        assert captured.get("system_id") == 3
        assert not captured.get("md5")
        assert not captured.get("sha1")
        assert not captured.get("crc")
        assert result["ss_id"] is None
        assert is_not_game is False

    @pytest.mark.asyncio
    async def test_no_hash_match_builds_game(self):
        """When jeuInfos matches an un-hashed file by filename, the game is built
        and returned (the romnom matcher bridges number-style differences such as
        'Adventure Island II' -> 'Adventure Island 2')."""
        config = _make_config(region_priority=["us"])
        game = {
            "id": "1234",
            "noms": [{"region": "us", "text": "Adventure Island 2"}],
            "medias": [],
            "synopsis": [],
            "dates": [],
            "genres": [],
            "familles": [],
            "modes": [],
            "joueurs": {},
            "note": {},
        }
        handler = SSHandler()
        mock_file = self._make_unhashed_file("Adventure Island II (USA).nes")
        rom = MagicMock(platform_slug="nes", platform_id=1, id=100, regions=["USA"])

        with (
            patch("handler.metadata.ss_handler.cm.get_config", return_value=config),
            patch.object(handler.ss_service, "get_game_info", return_value=game),
        ):
            result, is_not_game = await handler.lookup_rom(rom, 3, [mock_file])

        assert result["ss_id"] == 1234
        assert result["name"] == "Adventure Island 2"
        assert is_not_game is False

    @pytest.mark.asyncio
    async def test_no_hash_no_filename_skips_lookup(self):
        """With neither a hash nor a filename there is nothing to match on, so the
        lookup is skipped without spending an API call."""
        handler = SSHandler()
        mock_file = self._make_unhashed_file(file_name="")
        called = False

        async def capture(**kwargs):
            nonlocal called
            called = True
            return None

        with patch.object(handler.ss_service, "get_game_info", side_effect=capture):
            result, is_not_game = await handler.lookup_rom(
                MagicMock(platform_slug="nes"), 3, [mock_file]
            )

        assert called is False
        assert result["ss_id"] is None
        assert is_not_game is False

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
    async def test_romnom_uses_archive_member_name_for_single_file_archive(self):
        handler = SSHandler()
        mock_file = self._make_mock_file()
        mock_file.file_name = "Mario.zip"
        mock_file.archive_members = [
            {
                "name": "mario.n64",
                "size": 1024,
                "crc_hash": "",
                "md5_hash": "",
                "sha1_hash": "",
            }
        ]
        captured = {}

        async def capture(**kwargs):
            captured.update(kwargs)
            return None

        with patch.object(handler.ss_service, "get_game_info", side_effect=capture):
            await handler.lookup_rom(MagicMock(platform_slug="n64"), 14, [mock_file])
        assert captured.get("rom_name") == "mario.n64"

    @pytest.mark.asyncio
    async def test_romnom_uses_archive_filename_for_multi_file_archive(self):
        handler = SSHandler()
        mock_file = self._make_mock_file()
        mock_file.file_name = "Mario.zip"
        mock_file.archive_members = [
            {
                "name": "mario.bin",
                "size": 1024,
                "crc_hash": "",
                "md5_hash": "",
                "sha1_hash": "",
            },
            {
                "name": "mario.cue",
                "size": 64,
                "crc_hash": "",
                "md5_hash": "",
                "sha1_hash": "",
            },
        ]
        captured = {}

        async def capture(**kwargs):
            captured.update(kwargs)
            return None

        with patch.object(handler.ss_service, "get_game_info", side_effect=capture):
            await handler.lookup_rom(MagicMock(platform_slug="psx"), 57, [mock_file])
        assert captured.get("rom_name") == "Mario.zip"

    @pytest.mark.asyncio
    async def test_romnom_uses_archive_filename_when_no_archive_members(self):
        handler = SSHandler()
        mock_file = self._make_mock_file()
        mock_file.file_name = "mario.n64"
        mock_file.archive_members = None
        captured = {}

        async def capture(**kwargs):
            captured.update(kwargs)
            return None

        with patch.object(handler.ss_service, "get_game_info", side_effect=capture):
            await handler.lookup_rom(MagicMock(platform_slug="n64"), 14, [mock_file])
        assert captured.get("rom_name") == "mario.n64"

    @pytest.mark.asyncio
    async def test_romnom_uses_archive_filename_when_archive_members_empty(self):
        handler = SSHandler()
        mock_file = self._make_mock_file()
        mock_file.file_name = "Mario.zip"
        mock_file.archive_members = []
        captured = {}

        async def capture(**kwargs):
            captured.update(kwargs)
            return None

        with patch.object(handler.ss_service, "get_game_info", side_effect=capture):
            await handler.lookup_rom(MagicMock(platform_slug="n64"), 14, [mock_file])
        assert captured.get("rom_name") == "Mario.zip"

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


class TestSearchTermEncoding:
    """Regression tests for issue #3467: the SS name-search term must be
    URL-encoded exactly once.

    The handler must pass the *raw* (un-percent-encoded) term to the service
    layer, which percent-encodes it a single time when building the request URL
    via ``with_query(...)``. Pre-encoding the term in the handler caused a
    second round of encoding (``%2B`` -> ``%252B``), so ScreenScraper searched
    for literal gibberish and returned no match for any title containing a
    character that has to be URL-encoded (``+``, ``&``, an apostrophe, ...).
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("search_term", "literal", "double_encoded"),
        [
            ("super mario 3d world + bowsers fury", "+", "%2B"),
            ("sonic & knuckles", "&", "%26"),
            ("marvel's spider-man", "'", "%27"),
        ],
    )
    async def test_search_rom_passes_unencoded_term_to_service(
        self, search_term, literal, double_encoded
    ):
        """``_search_rom`` hands the service a term that is not pre-encoded."""
        handler = SSHandler()
        captured: dict = {}

        async def capture(**kwargs):
            captured.update(kwargs)
            return []

        with patch.object(handler.ss_service, "search_games", side_effect=capture):
            await handler._search_rom(search_term, 225)

        term = captured["term"]
        assert literal in term
        assert double_encoded not in term

    @pytest.mark.asyncio
    async def test_search_rom_still_transliterates_unicode(self):
        """Unidecode is still applied so accented titles match ScreenScraper."""
        handler = SSHandler()
        captured: dict = {}

        async def capture(**kwargs):
            captured.update(kwargs)
            return []

        with patch.object(handler.ss_service, "search_games", side_effect=capture):
            await handler._search_rom("Pokémon Snap", 14)

        assert captured["term"] == "Pokemon Snap"

    @pytest.mark.asyncio
    async def test_get_matched_roms_by_name_passes_unencoded_term(self):
        """``get_matched_roms_by_name`` also avoids pre-encoding the term."""
        handler = SSHandler()
        captured: dict = {}

        async def capture(**kwargs):
            captured.update(kwargs)
            return []

        with (
            patch("handler.metadata.ss_handler.SCREENSCRAPER_USER", "user1"),
            patch("handler.metadata.ss_handler.SCREENSCRAPER_PASSWORD", "pw1"),
            patch.object(handler.ss_service, "search_games", side_effect=capture),
        ):
            await handler.get_matched_roms_by_name(MagicMock(), "sonic & knuckles", 1)

        term = captured["term"]
        assert "&" in term
        assert "%26" not in term

    @pytest.mark.asyncio
    async def test_search_rom_url_single_encodes_plus(self):
        """End-to-end through the real service: a ``+`` is encoded exactly once
        in the request URL (``%2B``), never doubly (``%252B``)."""
        handler = SSHandler()
        captured: dict = {}

        async def capture_request(url, *args, **kwargs):
            captured["url"] = url
            return {"response": {"jeux": []}}

        with patch.object(handler.ss_service, "_request", side_effect=capture_request):
            await handler._search_rom("super mario 3d world + bowsers fury", 225)

        url = captured["url"]
        assert "%2B" in url
        assert "%252B" not in url
