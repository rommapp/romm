import hashlib
from pathlib import Path
from unittest.mock import Mock

import pytest
import socketio

from endpoints.sockets.scan import (
    ScanStats,
    _reconcile_relocated_roms,
    _should_scan_rom,
)
from handler.database import db_rom_handler
from handler.filesystem import fs_rom_handler
from handler.filesystem.roms_handler import FSRom, FSRomsHandler
from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from handler.scan_handler import ScanType
from models.platform import Platform
from models.rom import Rom


def test_scan_stats():
    stats = ScanStats()
    assert stats.scanned_platforms == 0
    assert stats.new_platforms == 0
    assert stats.identified_platforms == 0
    assert stats.scanned_roms == 0
    assert stats.new_roms == 0
    assert stats.identified_roms == 0
    assert stats.scanned_firmware == 0
    assert stats.new_firmware == 0

    stats.scanned_platforms += 1
    stats.new_platforms += 1
    stats.identified_platforms += 1
    stats.scanned_roms += 1
    stats.new_roms += 1
    stats.identified_roms += 1
    stats.scanned_firmware += 1
    stats.new_firmware += 1

    assert stats.scanned_platforms == 1
    assert stats.new_platforms == 1
    assert stats.identified_platforms == 1
    assert stats.scanned_roms == 1
    assert stats.new_roms == 1
    assert stats.identified_roms == 1
    assert stats.scanned_firmware == 1
    assert stats.new_firmware == 1


async def test_merging_scan_stats():
    stats = ScanStats(
        scanned_platforms=1,
        new_platforms=2,
        identified_platforms=3,
        scanned_roms=4,
        new_roms=5,
        identified_roms=6,
        scanned_firmware=7,
        new_firmware=8,
    )

    await stats.update(
        socket_manager=Mock(spec=socketio.AsyncRedisManager),
        scanned_platforms=stats.scanned_platforms + 10,
        new_platforms=stats.new_platforms + 11,
        identified_platforms=stats.identified_platforms + 12,
        scanned_roms=stats.scanned_roms + 13,
        new_roms=stats.new_roms + 14,
        identified_roms=stats.identified_roms + 15,
        scanned_firmware=stats.scanned_firmware + 16,
        new_firmware=stats.new_firmware + 17,
    )

    assert stats.scanned_platforms == 11
    assert stats.new_platforms == 13
    assert stats.identified_platforms == 15
    assert stats.scanned_roms == 17
    assert stats.new_roms == 19
    assert stats.identified_roms == 21
    assert stats.scanned_firmware == 23
    assert stats.new_firmware == 25


class TestShouldScanRom:
    def test_new_platforms_scan_with_no_rom(self):
        """NEW_PLATFORMS should scan when rom is None"""
        result = _should_scan_rom(ScanType.NEW_PLATFORMS, None, [], ["igdb"])
        assert result is True

    def test_new_platforms_scan_with_existing_rom(self, rom: Rom):
        """NEW_PLATFORMS should not scan when rom exists"""
        result = _should_scan_rom(ScanType.NEW_PLATFORMS, rom, [], ["igdb"])
        assert result is False

    # Test QUICK scan type
    def test_quick_scan_with_no_rom(self):
        """QUICK should scan when rom is None"""
        result = _should_scan_rom(ScanType.QUICK, None, [], ["igdb"])
        assert result is True

    def test_quick_scan_with_existing_rom(self, rom: Rom):
        """QUICK should not scan when rom exists"""
        result = _should_scan_rom(ScanType.QUICK, rom, [], ["igdb"])
        assert result is False

    # Test COMPLETE scan type
    def test_complete_scan_always_scans(self, rom: Rom):
        """COMPLETE should scan everything when unscoped, but respect roms_ids when scoped"""
        assert _should_scan_rom(ScanType.COMPLETE, None, [], ["igdb"]) is True
        assert _should_scan_rom(ScanType.COMPLETE, rom, [], ["igdb"]) is True
        # Scoped scan should not scan/add new filesystem ROMs when rom is None
        assert _should_scan_rom(ScanType.COMPLETE, None, [rom.id], ["igdb"]) is False
        # Scoped scan: rom not in list → skip even for COMPLETE
        assert (
            _should_scan_rom(ScanType.COMPLETE, rom, [rom.id + 99], ["igdb"]) is False
        )
        assert _should_scan_rom(ScanType.COMPLETE, rom, [rom.id], ["igdb"]) is True

    # Test HASHES scan type
    def test_hashes_scan_always_scans(self, rom: Rom):
        """HASHES should scan everything when unscoped, but respect roms_ids when scoped"""
        assert _should_scan_rom(ScanType.HASHES, None, [], ["igdb"]) is True
        assert _should_scan_rom(ScanType.HASHES, rom, [], ["igdb"]) is True
        # Scoped scan should not scan/add new filesystem ROMs when rom is None
        assert _should_scan_rom(ScanType.HASHES, None, [rom.id], ["igdb"]) is False
        # Scoped scan: rom not in list → skip even for HASHES
        assert _should_scan_rom(ScanType.HASHES, rom, [rom.id + 99], ["igdb"]) is False
        assert _should_scan_rom(ScanType.HASHES, rom, [rom.id], ["igdb"]) is True

    # Test UNMATCHED scan type
    def test_unmatched_scan_with_no_rom(self):
        """UNMATCHED should not scan when rom is None"""
        result = _should_scan_rom(ScanType.UNMATCHED, None, [], ["igdb"])
        assert result is False

    def test_unmatched_scan_with_unmatched_rom(self, rom: Rom):
        """UNMATCHED should scan when rom is unmatched"""
        rom.igdb_id = None
        rom.moby_id = None
        rom.ss_id = None
        rom.ra_id = None
        rom.launchbox_id = None
        result = _should_scan_rom(ScanType.UNMATCHED, rom, [], ["igdb"])
        assert result is True

    def test_unmatched_scan_with_identified_rom(self, rom: Rom):
        """UNMATCHED should also scan when rom is identified"""
        rom.igdb_id = 1
        result = _should_scan_rom(ScanType.UNMATCHED, rom, [], ["moby"])
        assert result is True

    # Test UPDATE scan type
    def test_update_scan_with_no_rom(self):
        """UPDATE should not scan when rom is None"""
        result = _should_scan_rom(ScanType.UPDATE, None, [], ["igdb"])
        assert result is False

    def test_update_scan_with_identified_rom(self, rom: Rom):
        """UPDATE should scan when rom is identified"""
        rom.igdb_id = 1
        result = _should_scan_rom(ScanType.UPDATE, rom, [], ["igdb"])
        assert result is True

    def test_update_scan_with_unmatched_rom(self, rom: Rom):
        """UPDATE should not scan when rom is not identified"""
        rom.igdb_id = None
        rom.moby_id = None
        rom.ss_id = None
        rom.ra_id = None
        rom.launchbox_id = None
        result = _should_scan_rom(ScanType.UPDATE, rom, [], ["igdb"])
        assert result is False

    # Test rom_ids parameter
    def test_scan_when_rom_id_in_list(self, rom: Rom):
        """Should scan when rom.id is in roms_ids list regardless of scan type"""
        rom.id = 1
        roms_ids = [1, 2, 3]

        # Test with different scan types
        for scan_type in [
            ScanType.QUICK,
            ScanType.UNMATCHED,
            ScanType.UPDATE,
        ]:
            result = _should_scan_rom(scan_type, rom, roms_ids, ["igdb"])
            assert result is True

    def test_no_scan_when_rom_id_not_in_list(self, rom: Rom):
        """When roms_ids is non-empty, scan is scoped: roms outside the list are skipped for every scan type"""
        rom.id = 4
        rom.igdb_id = None
        rom.moby_id = None
        rom.ss_id = None
        rom.ra_id = None
        rom.launchbox_id = None
        roms_ids = [1, 2, 3]

        for scan_type in [
            ScanType.NEW_PLATFORMS,
            ScanType.QUICK,
            ScanType.UPDATE,
            ScanType.UNMATCHED,
            ScanType.COMPLETE,
            ScanType.HASHES,
        ]:
            assert _should_scan_rom(scan_type, rom, roms_ids, ["igdb"]) is False

    # Edge cases
    def test_empty_roms_ids_list(self, rom: Rom):
        """Test behavior with empty roms_ids list"""
        rom.id = 1
        rom.igdb_id = 1

        assert _should_scan_rom(ScanType.UPDATE, rom, [], ["igdb"]) is True
        assert _should_scan_rom(ScanType.NEW_PLATFORMS, rom, [], ["igdb"]) is False

    def test_rom_id_type_conversion(self, rom: Rom):
        """Test that rom.id (int) is properly compared with roms_ids (list of strings)"""
        rom.id = 123
        roms_ids = [123, 456]

        # This should scan because 123 should match "123"
        result = _should_scan_rom(ScanType.QUICK, rom, roms_ids, ["igdb"])
        assert result is True

    @pytest.mark.parametrize(
        "scan_type,rom_exists,is_identified,rom_in_list,expected",
        [
            # Comprehensive test matrix
            (ScanType.NEW_PLATFORMS, False, None, False, False),
            (ScanType.NEW_PLATFORMS, True, True, False, False),
            (ScanType.NEW_PLATFORMS, True, True, True, True),
            (ScanType.QUICK, False, None, False, False),
            (ScanType.QUICK, True, True, False, False),
            (ScanType.COMPLETE, False, None, False, True),
            (ScanType.COMPLETE, True, False, False, True),
            (ScanType.HASHES, False, None, False, True),
            (ScanType.HASHES, True, False, False, True),
            (ScanType.UNMATCHED, True, False, False, True),
            (ScanType.UNMATCHED, True, True, False, False),
            (ScanType.UPDATE, True, True, False, True),
        ],
    )
    def test_comprehensive_scenarios(
        self,
        scan_type,
        rom_exists,
        is_identified,
        rom_in_list,
        expected,
    ):
        """Test comprehensive scenarios with different combinations"""
        rom: Rom = Mock(spec=Rom)
        roms_ids = []

        if rom_exists:
            rom.id = 1
            if is_identified:
                rom.igdb_id = 1
            else:
                rom.igdb_id = None
                rom.moby_id = None
                rom.ss_id = None
                rom.ra_id = None
                rom.launchbox_id = None

            if rom_in_list:
                roms_ids = [1]

        result = _should_scan_rom(scan_type, rom, roms_ids, ["igdb"])
        assert result is expected


class TestGetPico8CoverUrl:
    """Tests for the PICO-8 cover art URL helper on FSRomsHandler."""

    @pytest.fixture
    def handler(self):
        return FSRomsHandler()

    def test_returns_file_url_for_pico8_cartridge(self, handler: FSRomsHandler):
        url = handler.get_pico8_cover_url(
            platform_slug=UPS.PICO,
            fs_name="mygame.p8.png",
            fs_path="pico/roms",
        )
        expected = "file://pico/roms/mygame.p8.png"
        assert url == expected

    def test_returns_none_for_non_pico8_platform(self, handler: FSRomsHandler):
        url = handler.get_pico8_cover_url(
            platform_slug="snes",
            fs_name="mygame.p8.png",
            fs_path="snes/roms",
        )
        assert url is None

    def test_returns_none_for_plain_p8_text_file(self, handler: FSRomsHandler):
        """Plain .p8 files are text-only and have no embedded PNG image."""
        url = handler.get_pico8_cover_url(
            platform_slug=UPS.PICO,
            fs_name="mygame.p8",
            fs_path="pico/roms",
        )
        assert url is None

    def test_returns_none_for_unrelated_extension(self, handler: FSRomsHandler):
        url = handler.get_pico8_cover_url(
            platform_slug=UPS.PICO,
            fs_name="mygame.zip",
            fs_path="pico/roms",
        )
        assert url is None

    def test_url_starts_with_file_scheme(self, handler: FSRomsHandler):
        url = handler.get_pico8_cover_url(
            platform_slug=UPS.PICO,
            fs_name="cart.p8.png",
            fs_path="pico/roms",
        )
        assert url is not None
        assert url.startswith("file://")

    def test_url_contains_fs_path_and_name(self, handler: FSRomsHandler):
        fs_path = "pico/roms"
        fs_name = "celeste.p8.png"
        url = handler.get_pico8_cover_url(
            platform_slug=UPS.PICO,
            fs_name=fs_name,
            fs_path=fs_path,
        )
        assert url is not None
        assert fs_path in url
        assert fs_name in url


def _fs_rom(fs_name: str, fs_path: str) -> FSRom:
    return FSRom(
        fs_name=fs_name,
        fs_path=fs_path,
        flat=True,
        nested=False,
        files=[],
        crc_hash="",
        md5_hash="",
        sha1_hash="",
        ra_hash="",
    )


class TestReconcileRelocatedRoms:
    """A rom whose on-disk path changed (subfolder scanning) is relocated in
    place by content hash instead of being re-imported as new, so its DB row —
    and the saves/history/favorites/collections attached to it — survives."""

    @pytest.mark.asyncio
    async def test_moved_file_is_relocated_not_reimported(
        self, platform: Platform, tmp_path: Path, monkeypatch
    ):
        content = b"relocate me please"
        sha1 = hashlib.sha1(content, usedforsecurity=False).hexdigest()
        base = f"{platform.fs_slug}/roms"

        # An existing rom recorded at the platform root, with its content hash.
        rom = db_rom_handler.add_rom(
            Rom(
                platform_id=platform.id,
                name="Mover",
                slug="mover",
                fs_name="Mover.bin",
                fs_path=base,
                sha1_hash=sha1,
                fs_size_bytes=len(content),
            )
        )

        # On disk the file now lives inside a subfolder (same bytes).
        sub = tmp_path / base / "Hacks"
        sub.mkdir(parents=True)
        (sub / "Mover.bin").write_bytes(content)
        monkeypatch.setattr(fs_rom_handler, "base_path", tmp_path)

        fs_roms = [_fs_rom("Mover.bin", f"{base}/Hacks")]
        handled = await _reconcile_relocated_roms(platform, fs_roms)

        # The moved file is reported handled, so the scan loop skips it.
        assert handled == {f"{base}/Hacks/Mover.bin"}

        # Same row, new path, present again — not a fresh import.
        all_roms = db_rom_handler.get_roms_for_relocation(platform.id)
        assert len(all_roms) == 1
        updated = db_rom_handler.get_rom(rom.id)
        assert updated is not None
        assert updated.id == rom.id
        assert updated.fs_path == f"{base}/Hacks"
        assert updated.fs_name == "Mover.bin"
        assert updated.missing_from_fs is False

    @pytest.mark.asyncio
    async def test_no_hash_match_is_left_for_normal_import(
        self, platform: Platform, tmp_path: Path, monkeypatch
    ):
        base = f"{platform.fs_slug}/roms"
        # Existing rom whose stored hash won't match anything on disk.
        db_rom_handler.add_rom(
            Rom(
                platform_id=platform.id,
                name="Other",
                slug="other",
                fs_name="Other.bin",
                fs_path=base,
                sha1_hash=hashlib.sha1(b"unrelated", usedforsecurity=False).hexdigest(),
                fs_size_bytes=len(b"unrelated"),
            )
        )

        content = b"a brand new game entirely"
        sub = tmp_path / base / "Hacks"
        sub.mkdir(parents=True)
        (sub / "New.bin").write_bytes(content)
        monkeypatch.setattr(fs_rom_handler, "base_path", tmp_path)

        handled = await _reconcile_relocated_roms(
            platform, [_fs_rom("New.bin", f"{base}/Hacks")]
        )

        # Nothing relocated: the new file falls through to a normal import.
        assert handled == set()
