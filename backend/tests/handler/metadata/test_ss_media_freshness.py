"""Tests for ScreenScraper media freshness (issue #4002).

ScreenScraper publishes a `crc`/`md5`/`sha1` alongside every media entry in
`jeuInfos` so a client can tell whether the online file differs from its local
copy before downloading it. These tests cover extracting that hash and using it
to decide whether a stored resource is stale.
"""

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.services.screenscraper_types import SSGame
from config.config_manager import Config, MetadataMediaType
from handler.metadata.ss_handler import (
    SS_MEDIA_KEYS,
    extract_media_from_ss_game,
    ss_media_is_stale,
    ss_resource_needs_refresh,
)


def _make_config(scan_media: list[str] | None = None) -> Config:
    return Config(
        SCAN_REGION_MODE="prefer_rom_tags",
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
        SCAN_REGION_PRIORITY=[],
        SCAN_LANGUAGE_PRIORITY=["en"],
        SCAN_MEDIA=(
            scan_media if scan_media is not None else ["box2d", "logo", "screenshot"]
        ),
        GAMELIST_MEDIA_THUMBNAIL=MetadataMediaType.BOX2D,
        GAMELIST_MEDIA_IMAGE=MetadataMediaType.SCREENSHOT,
    )


def _make_rom() -> MagicMock:
    rom = MagicMock()
    rom.platform_id = 1
    rom.id = 100
    rom.regions = None
    return rom


def _media(
    media_type: str, url: str, md5: str | None = "aabbcc", region: str = "us"
) -> dict:
    entry = {
        "type": media_type,
        "parent": "jeu",
        "region": region,
        "url": url,
        "crc": "11223344",
        "sha1": "cafebabe",
        "size": "12345",
        "format": "png",
    }
    if md5 is not None:
        entry["md5"] = md5
    return entry


def _extract(game: SSGame, scan_media: list[str] | None = None):
    with (
        patch(
            "handler.metadata.ss_handler.cm.get_config",
            return_value=_make_config(scan_media),
        ),
        patch(
            "handler.metadata.ss_handler.fs_resource_handler.get_media_resources_path",
            side_effect=lambda pid, rid, mt: f"roms/{pid}/{rid}/{mt.value}",
        ),
    ):
        return extract_media_from_ss_game(_make_rom(), game)


class TestExtractMediaMd5:
    """`extract_media_from_ss_game` must carry each media entry's md5 through."""

    def test_md5_recorded_next_to_its_url(self):
        game = cast(
            SSGame,
            {
                "medias": [
                    _media("box-2D", "https://ss.example/box-2D", md5="COVERMD5"),
                    _media("wheel", "https://ss.example/wheel", md5="LOGOMD5"),
                ]
            },
        )

        result = _extract(game)

        assert result["box2d_url"] == "https://ss.example/box-2D"
        assert result["box2d_md5"] == "covermd5"
        assert result["logo_url"] == "https://ss.example/wheel"
        assert result["logo_md5"] == "logomd5"

    def test_md5_matches_the_selected_region(self):
        """The hash must belong to the media entry that actually won."""
        game = cast(
            SSGame,
            {
                "medias": [
                    _media(
                        "box-2D",
                        "https://ss.example/box-2D(cus)",
                        md5="cusmd5",
                        region="cus",
                    ),
                    _media(
                        "box-2D",
                        "https://ss.example/box-2D(us)",
                        md5="usmd5",
                        region="us",
                    ),
                ]
            },
        )

        result = _extract(game)

        assert result["box2d_url"] == "https://ss.example/box-2D(us)"
        assert result["box2d_md5"] == "usmd5"

    def test_md5_recorded_for_urls_with_credentials_stripped(self):
        """URLs are stored stripped of credentials; the md5 must still line up."""
        game = cast(
            SSGame,
            {
                "medias": [
                    _media(
                        "box-2D",
                        "https://screenscraper.fr/api2/mediaJeu.php?ssid=u&sspassword=p&media=box-2D",
                        md5="strippedmd5",
                    )
                ]
            },
        )

        result = _extract(game)

        assert result["box2d_url"] is not None
        assert "sspassword" not in result["box2d_url"]
        assert result["box2d_md5"] == "strippedmd5"

    def test_missing_md5_is_none(self):
        game = cast(
            SSGame,
            {"medias": [_media("box-2D", "https://ss.example/box-2D", md5=None)]},
        )

        result = _extract(game)

        assert result["box2d_url"] == "https://ss.example/box-2D"
        assert result["box2d_md5"] is None

    def test_every_media_key_has_an_md5_slot(self):
        """Absent media leave their md5 slot present but empty."""
        result = _extract(cast(SSGame, {"medias": []}))

        for key in SS_MEDIA_KEYS:
            assert f"{key}_md5" in result, f"{key}_md5 missing from extracted media"
            assert result[f"{key}_md5"] is None  # type: ignore[literal-required]

    def test_size_recorded_next_to_its_url(self):
        game = cast(
            SSGame,
            {"medias": [_media("box-2D", "https://ss.example/box-2D", md5="covermd5")]},
        )

        result = _extract(game)

        assert result["box2d_size"] == 12345

    def test_size_matches_the_selected_region(self):
        """ScreenScraper lists one entry per region; only the winner's size counts."""
        game = cast(
            SSGame,
            {
                "medias": [
                    {
                        **_media("box-2D", "https://ss.example/(cus)", region="cus"),
                        "size": "111",
                    },
                    {
                        **_media("box-2D", "https://ss.example/(us)", region="us"),
                        "size": "222",
                    },
                ]
            },
        )

        result = _extract(game)

        assert result["box2d_url"] == "https://ss.example/(us)"
        assert result["box2d_size"] == 222

    @pytest.mark.parametrize("bad", ["", "not-a-number", None])
    def test_unusable_size_is_none(self, bad):
        entry = _media("box-2D", "https://ss.example/box-2D")
        if bad is None:
            entry.pop("size")
        else:
            entry["size"] = bad

        result = _extract(cast(SSGame, {"medias": [entry]}))

        assert result["box2d_size"] is None
        assert result["box2d_md5"] == "aabbcc"


class TestSSMediaIsStale:
    """The staleness rule that decides whether a stored resource is refetched."""

    @pytest.fixture(autouse=True)
    def _no_disk(self):
        """Default: nothing on disk matches, so only the recorded hash can decide."""
        with patch(
            "handler.metadata.ss_handler.fs_resource_handler.file_matches_md5",
            AsyncMock(return_value=False),
        ) as mock:
            yield mock

    async def test_no_fresh_hash_is_never_stale(self):
        """Without a hash from ScreenScraper there is nothing to compare."""
        assert not await ss_media_is_stale("roms/1/1/logo/logo.png", "abc", None)

    async def test_unchanged_recorded_hash_is_not_stale(self, _no_disk):
        assert not await ss_media_is_stale("roms/1/1/logo/logo.png", "abc", "abc")
        _no_disk.assert_not_awaited()

    async def test_recorded_hash_comparison_is_case_insensitive(self):
        assert not await ss_media_is_stale("roms/1/1/logo/logo.png", "ABC", "abc")

    async def test_changed_recorded_hash_is_stale(self):
        assert await ss_media_is_stale("roms/1/1/logo/logo.png", "abc", "def")

    async def test_missing_recorded_hash_falls_back_to_the_file_on_disk(self, _no_disk):
        """Libraries scanned before hashes existed must not redownload for nothing."""
        _no_disk.return_value = True

        assert not await ss_media_is_stale("roms/1/1/logo/logo.png", None, "abc")
        _no_disk.assert_awaited_once_with("roms/1/1/logo/logo.png", "abc")

    async def test_missing_recorded_hash_with_differing_file_is_stale(self):
        assert await ss_media_is_stale("roms/1/1/logo/logo.png", None, "abc")

    async def test_stale_recorded_hash_is_rescued_by_a_matching_file(self, _no_disk):
        """A recorded hash that disagrees with a matching file is not a redownload."""
        _no_disk.return_value = True

        assert not await ss_media_is_stale("roms/1/1/logo/logo.png", "old", "abc")

    async def test_no_stored_path_is_stale(self, _no_disk):
        """Nothing on disk to compare against, so the media has to be fetched."""
        assert await ss_media_is_stale(None, None, "abc")
        _no_disk.assert_not_awaited()


class TestSSMediaSizeCheck:
    """A partial download is caught by size before the recorded hash is trusted.

    The hash is recorded when the ROM row is written, which happens before the
    download runs, so a scan killed mid-stream leaves a short file that the
    recorded hash still claims is current.
    """

    PATH = "roms/1/1/cover/big.png"

    @pytest.fixture
    def disk(self):
        with (
            patch(
                "handler.metadata.ss_handler.fs_resource_handler.file_has_size",
                AsyncMock(return_value=True),
            ) as size_mock,
            patch(
                "handler.metadata.ss_handler.fs_resource_handler.file_matches_md5",
                AsyncMock(return_value=False),
            ) as md5_mock,
        ):
            yield size_mock, md5_mock

    async def test_short_file_is_stale_despite_a_matching_hash(self, disk):
        size_mock, md5_mock = disk
        size_mock.return_value = False

        assert await ss_media_is_stale(self.PATH, "abc", "abc", 1234)
        size_mock.assert_awaited_once_with(self.PATH, 1234)
        md5_mock.assert_not_awaited()

    async def test_correct_size_keeps_the_cheap_hash_shortcut(self, disk):
        size_mock, md5_mock = disk

        assert not await ss_media_is_stale(self.PATH, "abc", "abc", 1234)
        md5_mock.assert_not_awaited()

    async def test_no_reported_size_skips_the_check(self, disk):
        size_mock, _ = disk

        assert not await ss_media_is_stale(self.PATH, "abc", "abc", None)
        size_mock.assert_not_awaited()

    async def test_no_stored_path_skips_the_check(self, disk):
        """With no file to stat, the recorded hash decides as it did before."""
        size_mock, _ = disk

        assert not await ss_media_is_stale(None, "abc", "abc", 1234)
        size_mock.assert_not_awaited()


class TestSSResourceNeedsRefresh:
    """Cover/screenshot refresh, which only applies when SS is the source."""

    def _refresh(self, **overrides: Any):
        kwargs: dict[str, Any] = {
            "previous_metadata": {"box2d_md5": "old"},
            "fresh_metadata": {
                "box2d_url": "https://ss.example/box-2D",
                "box2d_md5": "new",
            },
            "media_key": "box2d",
            "resolved_url": "https://ss.example/box-2D",
            "stored_path": "roms/1/1/cover/big.png",
        }
        kwargs.update(overrides)
        return ss_resource_needs_refresh(**kwargs)

    @pytest.fixture(autouse=True)
    def _no_disk(self):
        with patch(
            "handler.metadata.ss_handler.fs_resource_handler.file_matches_md5",
            AsyncMock(return_value=False),
        ) as mock:
            yield mock

    async def test_changed_hash_triggers_a_refresh(self):
        assert await self._refresh()

    async def test_unchanged_hash_does_not(self):
        assert not await self._refresh(previous_metadata={"box2d_md5": "new"})

    async def test_another_provider_won_the_field(self):
        """SS's hash says nothing about a cover IGDB supplied."""
        assert not await self._refresh(resolved_url="https://igdb.example/cover.jpg")

    async def test_no_ss_media_for_that_key(self):
        assert not await self._refresh(fresh_metadata={})

    async def test_no_stored_metadata_at_all(self):
        assert not await self._refresh(fresh_metadata=None)

    async def test_missing_resolved_url(self):
        assert not await self._refresh(resolved_url=None)
