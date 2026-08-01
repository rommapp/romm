"""Update scans must refresh stale ScreenScraper resources (issue #4002).

ScreenScraper media URLs are fixed endpoints, so the URL-diff gate that guards
the cover and screenshot downloads can never fire for it. These tests drive
`_identify_rom` through an UPDATE scan and assert the md5 ScreenScraper reports
is what decides whether a resource is refetched.
"""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from endpoints.sockets import scan as scan_module
from endpoints.sockets.scan import _identify_rom
from handler.filesystem.roms_handler import FSRom, ParsedRomFiles, ParsedTags
from handler.scan_handler import MetadataSource, ScanType
from models.platform import Platform

COVER_URL = "https://screenscraper.fr/api2/mediaJeu.php?media=box-2D"
LOGO_URL = "https://screenscraper.fr/api2/mediaJeu.php?media=wheel"


def _ss_metadata(cover_md5: str, logo_md5: str) -> dict:
    return {
        "box2d_url": COVER_URL,
        "box2d_md5": cover_md5,
        "logo_url": LOGO_URL,
        "logo_md5": logo_md5,
        "logo_path": "roms/1/42/logo/logo.png",
    }


class TestUpdateScanRefreshesScreenScraperMedia:
    @pytest.fixture
    def resources(self, mocker):
        resources = mocker.patch.object(scan_module, "fs_resource_handler")
        resources.get_cover = AsyncMock(return_value=("small.png", "big.png"))
        resources.get_manual = AsyncMock(return_value="manual.pdf")
        resources.get_rom_screenshots = AsyncMock(return_value=[])
        resources.store_media_file = AsyncMock()
        resources.get_downloaded_cover_path = Mock(
            return_value="roms/1/42/cover/big.png"
        )
        return resources

    @pytest.fixture
    def patched(self, mocker, resources):
        mocker.patch.object(
            scan_module, "redis_client", Mock(get=Mock(return_value=None))
        )

        fs = scan_module.fs_rom_handler
        mocker.patch.object(
            fs,
            "parse_tags",
            return_value=ParsedTags(
                version="", revision="", regions=[], languages=[], other_tags=[]
            ),
        )
        mocker.patch.object(fs, "get_roms_fs_structure", return_value="test/roms")
        mocker.patch.object(fs, "get_file_name_with_no_tags", return_value="Game")
        mocker.patch.object(
            fs,
            "get_rom_files",
            AsyncMock(
                return_value=ParsedRomFiles(
                    rom_files=[], crc_hash="", md5_hash="", sha1_hash="", ra_hash=""
                )
            ),
        )

        config = MagicMock()
        config.SKIP_HASH_CALCULATION = True
        mocker.patch.object(scan_module.cm, "get_config", return_value=config)
        mocker.patch.object(
            scan_module,
            "get_preferred_media_types",
            return_value=[scan_module.MetadataMediaType.LOGO],
        )

        # The closing emit serializes the ROM, which these stand-ins can't satisfy.
        mocker.patch.object(scan_module, "SimpleRomSchema")

        db = mocker.patch.object(scan_module, "db_rom_handler")
        return db

    def _stored_rom(self, ss_metadata: dict):
        """The ROM as it sits in the database before the scan."""
        return MagicMock(
            id=42,
            fs_name="Game.zip",
            fs_path="test/roms",
            url_cover=COVER_URL,
            url_manual="",
            url_screenshots=[],
            path_cover_s="roms/1/42/cover/small.png",
            path_cover_l="roms/1/42/cover/big.png",
            path_screenshots=[],
            path_manual="",
            ss_metadata=ss_metadata,
        )

    def _scanned_rom(self, ss_metadata: dict):
        """What the scan produced, with a freshly fetched ScreenScraper blob."""
        return MagicMock(
            id=42,
            is_identified=True,
            url_cover=COVER_URL,
            url_manual="",
            url_screenshots=[],
            path_cover_s="roms/1/42/cover/small.png",
            path_cover_l="roms/1/42/cover/big.png",
            path_screenshots=[],
            path_manual="",
            ss_metadata=ss_metadata,
        )

    async def _run(self, mocker, db, stored, scanned):
        mocker.patch.object(scan_module, "scan_rom", AsyncMock(return_value=scanned))
        db.add_rom.return_value = scanned
        db.sync_rom_files.return_value = MagicMock(files=[], orphaned_cover_paths=[])

        platform = Platform(name="Test", slug="test", fs_slug="test")
        platform.id = 1
        fs_rom: FSRom = {
            "fs_name": "Game.zip",
            "flat": True,
            "nested": False,
            "files": [],
            "crc_hash": "",
            "md5_hash": "",
            "sha1_hash": "",
            "ra_hash": "",
        }

        await _identify_rom(
            platform=platform,
            fs_rom=fs_rom,
            rom=stored,
            scan_type=ScanType.UPDATE,
            roms_ids=[],
            metadata_sources=[MetadataSource.SS],
            launchbox_remote_enabled=False,
            playmatch_enabled=False,
            socket_manager=AsyncMock(),
            scan_stats=AsyncMock(),
        )

    async def test_cover_is_refetched_when_screenscraper_reports_a_new_hash(
        self, mocker, patched, resources
    ):
        stored = self._stored_rom(_ss_metadata("oldcover", "logo1"))
        scanned = self._scanned_rom(_ss_metadata("newcover", "logo1"))

        await self._run(mocker, patched, stored, scanned)

        assert resources.get_cover.await_args.kwargs["overwrite"] is True

    async def test_cover_is_left_alone_when_the_hash_is_unchanged(
        self, mocker, patched, resources
    ):
        stored = self._stored_rom(_ss_metadata("samecover", "logo1"))
        scanned = self._scanned_rom(_ss_metadata("samecover", "logo1"))

        await self._run(mocker, patched, stored, scanned)

        assert resources.get_cover.await_args.kwargs["overwrite"] is False

    async def test_extra_media_downloads_carry_the_expected_hash(
        self, mocker, patched, resources
    ):
        """`store_media_file` needs the hash to tell a stale file from a current one."""
        stored = self._stored_rom(_ss_metadata("cover1", "logo1"))
        scanned = self._scanned_rom(_ss_metadata("cover1", "logo2"))

        await self._run(mocker, patched, stored, scanned)

        resources.store_media_file.assert_awaited_once()
        assert resources.store_media_file.await_args.kwargs["expected_md5"] == "logo2"
