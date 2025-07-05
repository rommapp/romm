from unittest.mock import Mock

import pytest
from handler.scan_handler import ScanType
from models.rom import Rom

from ..scan import ScanStats, _should_scan_rom


def test_scan_stats():
    stats = ScanStats()
    assert stats.scanned_platforms == 0
    assert stats.added_platforms == 0
    assert stats.metadata_platforms == 0
    assert stats.scanned_roms == 0
    assert stats.added_roms == 0
    assert stats.metadata_roms == 0
    assert stats.scanned_firmware == 0
    assert stats.added_firmware == 0

    stats.scanned_platforms += 1
    stats.added_platforms += 1
    stats.metadata_platforms += 1
    stats.scanned_roms += 1
    stats.added_roms += 1
    stats.metadata_roms += 1
    stats.scanned_firmware += 1
    stats.added_firmware += 1

    assert stats.scanned_platforms == 1
    assert stats.added_platforms == 1
    assert stats.metadata_platforms == 1
    assert stats.scanned_roms == 1
    assert stats.added_roms == 1
    assert stats.metadata_roms == 1
    assert stats.scanned_firmware == 1
    assert stats.added_firmware == 1


def test_merging_scan_stats():
    stats = ScanStats(
        scanned_platforms=1,
        added_platforms=2,
        metadata_platforms=3,
        scanned_roms=4,
        added_roms=5,
        metadata_roms=6,
        scanned_firmware=7,
        added_firmware=8,
    )

    stats2 = ScanStats(
        scanned_platforms=10,
        added_platforms=11,
        metadata_platforms=12,
        scanned_roms=13,
        added_roms=14,
        metadata_roms=15,
        scanned_firmware=16,
        added_firmware=17,
    )

    stats += stats2

    assert stats.scanned_platforms == 11
    assert stats.added_platforms == 13
    assert stats.metadata_platforms == 15
    assert stats.scanned_roms == 17
    assert stats.added_roms == 19
    assert stats.metadata_roms == 21
    assert stats.scanned_firmware == 23
    assert stats.added_firmware == 25

    stats3: dict = {}
    with pytest.raises(NotImplementedError):
        stats += stats3


class TestShouldScanRom:
    def test_new_platforms_scan_with_no_rom(self):
        """NEW_PLATFORMS should scan when rom is None"""
        result = _should_scan_rom(ScanType.NEW_PLATFORMS, None, [])
        assert result is True

    def test_new_platforms_scan_with_existing_rom(self, rom: Rom):
        """NEW_PLATFORMS should not scan when rom exists"""
        result = _should_scan_rom(ScanType.NEW_PLATFORMS, rom, [])
        assert result is False

    # Test QUICK scan type
    def test_quick_scan_with_no_rom(self):
        """QUICK should scan when rom is None"""
        result = _should_scan_rom(ScanType.QUICK, None, [])
        assert result is True

    def test_quick_scan_with_existing_rom(self, rom: Rom):
        """QUICK should not scan when rom exists"""
        result = _should_scan_rom(ScanType.QUICK, rom, [])
        assert result is False

    # Test COMPLETE scan type
    def test_complete_scan_always_scans(self, rom: Rom):
        """COMPLETE should always scan regardless of rom state"""
        assert _should_scan_rom(ScanType.COMPLETE, None, []) is True
        assert _should_scan_rom(ScanType.COMPLETE, rom, []) is True
        assert _should_scan_rom(ScanType.COMPLETE, rom, ["2", "3"]) is True

    # Test HASHES scan type
    def test_hashes_scan_always_scans(self, rom: Rom):
        """HASHES should always scan regardless of rom state"""
        assert _should_scan_rom(ScanType.HASHES, None, []) is True
        assert _should_scan_rom(ScanType.HASHES, rom, []) is True
        assert _should_scan_rom(ScanType.HASHES, rom, ["2", "3"]) is True

    # Test UNIDENTIFIED scan type
    def test_unidentified_scan_with_no_rom(self):
        """UNIDENTIFIED should not scan when rom is None"""
        result = _should_scan_rom(ScanType.UNIDENTIFIED, None, [])
        assert result is False

    def test_unidentified_scan_with_unidentified_rom(self, rom: Rom):
        """UNIDENTIFIED should scan when rom is unidentified"""
        rom.igdb_id = None
        rom.moby_id = None
        rom.ss_id = None
        rom.ra_id = None
        rom.launchbox_id = None
        result = _should_scan_rom(ScanType.UNIDENTIFIED, rom, [])
        assert result is True

    def test_unidentified_scan_with_identified_rom(self, rom: Rom):
        """UNIDENTIFIED should not scan when rom is identified"""
        rom.igdb_id = 1
        result = _should_scan_rom(ScanType.UNIDENTIFIED, rom, [])
        assert result is False

    # Test PARTIAL scan type
    def test_partial_scan_with_no_rom(self):
        """PARTIAL should not scan when rom is None"""
        result = _should_scan_rom(ScanType.PARTIAL, None, [])
        assert result is False

    def test_partial_scan_with_identified_rom(self, rom: Rom):
        """PARTIAL should scan when rom is identified"""
        rom.igdb_id = 1
        result = _should_scan_rom(ScanType.PARTIAL, rom, [])
        assert result is True

    def test_partial_scan_with_unidentified_rom(self, rom: Rom):
        """PARTIAL should not scan when rom is not identified"""
        rom.igdb_id = None
        rom.moby_id = None
        rom.ss_id = None
        rom.ra_id = None
        rom.launchbox_id = None
        result = _should_scan_rom(ScanType.PARTIAL, rom, [])
        assert result is False

    # Test rom_ids parameter
    def test_scan_when_rom_id_in_list(self, rom: Rom):
        """Should scan when rom.id is in roms_ids list regardless of scan type"""
        rom.id = 1
        roms_ids = ["1", "2", "3"]

        # Test with different scan types
        for scan_type in [
            ScanType.NEW_PLATFORMS,
            ScanType.QUICK,
            ScanType.UNIDENTIFIED,
            ScanType.PARTIAL,
        ]:
            result = _should_scan_rom(scan_type, rom, roms_ids)
            assert result is True

    def test_no_scan_when_rom_id_not_in_list(self, rom: Rom):
        """Should follow normal rules when rom.id is not in roms_ids list"""
        rom.id = 4
        roms_ids = ["1", "2", "3"]

        # These should not scan because rom exists and id not in list
        assert _should_scan_rom(ScanType.NEW_PLATFORMS, rom, roms_ids) is False
        assert _should_scan_rom(ScanType.QUICK, rom, roms_ids) is False
        assert _should_scan_rom(ScanType.UNIDENTIFIED, rom, roms_ids) is False
        assert _should_scan_rom(ScanType.PARTIAL, rom, roms_ids) is False

    # Edge cases
    def test_empty_roms_ids_list(self, rom: Rom):
        """Test behavior with empty roms_ids list"""
        rom.id = 1
        rom.igdb_id = 1

        assert _should_scan_rom(ScanType.PARTIAL, rom, []) is True
        assert _should_scan_rom(ScanType.NEW_PLATFORMS, rom, []) is False

    def test_rom_id_type_conversion(self, rom: Rom):
        """Test that rom.id (int) is properly compared with roms_ids (list of strings)"""
        rom.id = 123
        roms_ids = ["123", "456"]

        # This should scan because 123 should match "123"
        result = _should_scan_rom(ScanType.NEW_PLATFORMS, rom, roms_ids)
        assert result is True

    @pytest.mark.parametrize(
        "scan_type,rom_exists,is_identified,rom_in_list,expected",
        [
            # Comprehensive test matrix
            (ScanType.NEW_PLATFORMS, False, None, False, True),
            (ScanType.NEW_PLATFORMS, True, True, False, False),
            (ScanType.NEW_PLATFORMS, True, True, True, True),
            (ScanType.QUICK, False, None, False, True),
            (ScanType.QUICK, True, True, False, False),
            (ScanType.COMPLETE, False, None, False, True),
            (ScanType.COMPLETE, True, False, False, True),
            (ScanType.HASHES, False, None, False, True),
            (ScanType.HASHES, True, False, False, True),
            (ScanType.UNIDENTIFIED, True, False, False, True),
            (ScanType.UNIDENTIFIED, True, True, False, False),
            (ScanType.PARTIAL, True, True, False, True),
            (ScanType.PARTIAL, True, True, False, False),
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
                roms_ids = ["1"]

        result = _should_scan_rom(scan_type, rom, roms_ids)
        assert result is expected
