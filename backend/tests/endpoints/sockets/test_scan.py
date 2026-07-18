from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
import socketio

from endpoints.sockets import scan as scan_module
from endpoints.sockets.scan import (
    ScanStats,
    reject_unauthorized_scan,
    scan_handler,
    scan_platforms,
    should_scan_rom,
    stop_scan_handler,
)
from handler.auth.constants import Scope
from handler.filesystem.roms_handler import FSRomsHandler
from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from handler.scan_handler import ScanType
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


class TestScanTotals:
    """The scan tracker totals must reflect the platforms/roms actually scanned."""

    @pytest.fixture
    def patched(self, mocker):
        """Patch the collaborators of scan_platforms so totals can be inspected."""
        socket_manager = AsyncMock()
        mocker.patch.object(
            scan_module, "_get_socket_manager", return_value=socket_manager
        )
        mocker.patch.object(
            scan_module.fs_platform_handler,
            "get_platforms",
            AsyncMock(return_value=["existing", "new1", "new2"]),
        )
        # Each platform reports 100 roms on disk.
        mocker.patch.object(
            scan_module.fs_rom_handler, "count_roms", AsyncMock(return_value=100)
        )
        mocker.patch.object(scan_module.meta_gamelist_handler, "clear_cache")
        mocker.patch.object(
            scan_module.db_platform_handler, "mark_missing_platforms", return_value=[]
        )
        # The "existing" platform is already in the database; "new1"/"new2" are not.
        existing_platform = MagicMock(id=1, fs_slug="existing")
        mocker.patch.object(
            scan_module.db_platform_handler,
            "get_platforms",
            return_value=[existing_platform],
        )
        mocker.patch.object(
            scan_module.db_rom_handler, "invalidate_filter_values_cache"
        )
        config = MagicMock()
        config.GAMELIST_AUTO_EXPORT_ON_SCAN = False
        config.PEGASUS_AUTO_EXPORT_ON_SCAN = False
        mocker.patch.object(scan_module.cm, "get_config", return_value=config)

        # Skip the actual per-platform scanning, returning the stats unchanged.
        async def fake_identify(**kwargs):
            return kwargs["scan_stats"]

        mocker.patch.object(
            scan_module, "_identify_platform", side_effect=fake_identify
        )
        return socket_manager

    async def test_new_platforms_total_excludes_existing(self, patched, mocker):
        """NEW_PLATFORMS totals must skip platforms already in the database."""
        result = await scan_platforms(
            platform_ids=[],
            metadata_sources=[],
            scan_type=ScanType.NEW_PLATFORMS,
        )

        # Only the two new platforms (and their roms) should be counted.
        assert result.total_platforms == 2
        assert result.total_roms == 200

    async def test_complete_scan_counts_all_selected(self, patched, mocker):
        """COMPLETE totals include every filesystem platform being scanned."""
        mocker.patch.object(
            scan_module.db_platform_handler,
            "get_platform_by_fs_slug",
            return_value=MagicMock(),
        )

        result = await scan_platforms(
            platform_ids=[],
            metadata_sources=[],
            scan_type=ScanType.COMPLETE,
        )

        assert result.total_platforms == 3
        assert result.total_roms == 300


class TestShouldScanRom:
    def test_new_platforms_scan_with_no_rom(self):
        """NEW_PLATFORMS should scan when rom is None"""
        result = should_scan_rom(ScanType.NEW_PLATFORMS, None, [], ["igdb"])
        assert result is True

    def test_new_platforms_scan_with_existing_rom(self, rom: Rom):
        """NEW_PLATFORMS should not scan when rom exists"""
        result = should_scan_rom(ScanType.NEW_PLATFORMS, rom, [], ["igdb"])
        assert result is False

    # Test QUICK scan type
    def test_quick_scan_with_no_rom(self):
        """QUICK should scan when rom is None"""
        result = should_scan_rom(ScanType.QUICK, None, [], ["igdb"])
        assert result is True

    def test_quick_scan_with_existing_rom(self, rom: Rom):
        """QUICK should not scan when rom exists"""
        result = should_scan_rom(ScanType.QUICK, rom, [], ["igdb"])
        assert result is False

    # Test COMPLETE scan type
    def test_complete_scan_always_scans(self, rom: Rom):
        """COMPLETE should scan everything when unscoped, but respect roms_ids when scoped"""
        assert should_scan_rom(ScanType.COMPLETE, None, [], ["igdb"]) is True
        assert should_scan_rom(ScanType.COMPLETE, rom, [], ["igdb"]) is True
        # Scoped scan should not scan/add new filesystem ROMs when rom is None
        assert should_scan_rom(ScanType.COMPLETE, None, [rom.id], ["igdb"]) is False
        # Scoped scan: rom not in list → skip even for COMPLETE
        assert should_scan_rom(ScanType.COMPLETE, rom, [rom.id + 99], ["igdb"]) is False
        assert should_scan_rom(ScanType.COMPLETE, rom, [rom.id], ["igdb"]) is True

    # Test HASHES scan type
    def test_hashes_scan_always_scans(self, rom: Rom):
        """HASHES should scan everything when unscoped, but respect roms_ids when scoped"""
        assert should_scan_rom(ScanType.HASHES, None, [], ["igdb"]) is True
        assert should_scan_rom(ScanType.HASHES, rom, [], ["igdb"]) is True
        # Scoped scan should not scan/add new filesystem ROMs when rom is None
        assert should_scan_rom(ScanType.HASHES, None, [rom.id], ["igdb"]) is False
        # Scoped scan: rom not in list → skip even for HASHES
        assert should_scan_rom(ScanType.HASHES, rom, [rom.id + 99], ["igdb"]) is False
        assert should_scan_rom(ScanType.HASHES, rom, [rom.id], ["igdb"]) is True

    # Test UNMATCHED scan type
    def test_unmatched_scan_with_no_rom(self):
        """UNMATCHED should not scan when rom is None"""
        result = should_scan_rom(ScanType.UNMATCHED, None, [], ["igdb"])
        assert result is False

    def test_unmatched_scan_with_unmatched_rom(self, rom: Rom):
        """UNMATCHED should scan when rom is unmatched"""
        rom.igdb_id = None
        rom.moby_id = None
        rom.ss_id = None
        rom.ra_id = None
        rom.launchbox_id = None
        result = should_scan_rom(ScanType.UNMATCHED, rom, [], ["igdb"])
        assert result is True

    def test_unmatched_scan_with_identified_rom(self, rom: Rom):
        """UNMATCHED should also scan when rom is identified"""
        rom.igdb_id = 1
        result = should_scan_rom(ScanType.UNMATCHED, rom, [], ["moby"])
        assert result is True

    # Test UPDATE scan type
    def test_update_scan_with_no_rom(self):
        """UPDATE should not scan when rom is None"""
        result = should_scan_rom(ScanType.UPDATE, None, [], ["igdb"])
        assert result is False

    def test_update_scan_with_identified_rom(self, rom: Rom):
        """UPDATE should scan when rom is identified"""
        rom.igdb_id = 1
        result = should_scan_rom(ScanType.UPDATE, rom, [], ["igdb"])
        assert result is True

    def test_update_scan_with_unmatched_rom(self, rom: Rom):
        """UPDATE should not scan when rom is not identified"""
        rom.igdb_id = None
        rom.moby_id = None
        rom.ss_id = None
        rom.ra_id = None
        rom.launchbox_id = None
        result = should_scan_rom(ScanType.UPDATE, rom, [], ["igdb"])
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
            result = should_scan_rom(scan_type, rom, roms_ids, ["igdb"])
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
            assert should_scan_rom(scan_type, rom, roms_ids, ["igdb"]) is False

    # Edge cases
    def test_empty_roms_ids_list(self, rom: Rom):
        """Test behavior with empty roms_ids list"""
        rom.id = 1
        rom.igdb_id = 1

        assert should_scan_rom(ScanType.UPDATE, rom, [], ["igdb"]) is True
        assert should_scan_rom(ScanType.NEW_PLATFORMS, rom, [], ["igdb"]) is False

    def test_rom_id_type_conversion(self, rom: Rom):
        """Test that rom.id (int) is properly compared with roms_ids (list of strings)"""
        rom.id = 123
        roms_ids = [123, 456]

        # This should scan because 123 should match "123"
        result = should_scan_rom(ScanType.QUICK, rom, roms_ids, ["igdb"])
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

        result = should_scan_rom(scan_type, rom, roms_ids, ["igdb"])
        assert result is expected


class TestScanAuthorization:
    """The scan/scan:stop socket handlers must require the TASKS_RUN scope."""

    @pytest.fixture
    def emit(self, mocker):
        emit = AsyncMock()
        mocker.patch.object(scan_module.socket_handler.socket_server, "emit", emit)
        return emit

    def _user(self, *scopes):
        user = MagicMock()
        user.oauth_scopes = list(scopes)
        return user

    async def test_reject_unauthenticated(self, mocker, emit):
        mocker.patch.object(
            scan_module, "get_authenticated_user", AsyncMock(return_value=None)
        )
        assert await reject_unauthorized_scan("sid") is True
        emit.assert_awaited_once()

    async def test_reject_user_without_tasks_run(self, mocker, emit):
        mocker.patch.object(
            scan_module,
            "get_authenticated_user",
            AsyncMock(return_value=self._user(Scope.ROMS_READ)),
        )
        assert await reject_unauthorized_scan("sid") is True
        emit.assert_awaited_once()

    async def test_allow_user_with_tasks_run(self, mocker, emit):
        mocker.patch.object(
            scan_module,
            "get_authenticated_user",
            AsyncMock(return_value=self._user(Scope.TASKS_RUN)),
        )
        assert await reject_unauthorized_scan("sid") is False
        emit.assert_not_awaited()

    async def test_scan_handler_does_not_enqueue_when_unauthorized(self, mocker, emit):
        mocker.patch.object(
            scan_module, "get_authenticated_user", AsyncMock(return_value=None)
        )
        enqueue = mocker.patch.object(scan_module.high_prio_queue, "enqueue")
        scan_platforms_mock = mocker.patch.object(
            scan_module, "scan_platforms", AsyncMock()
        )

        await scan_handler("sid", {"type": "complete"})

        enqueue.assert_not_called()
        scan_platforms_mock.assert_not_awaited()

    async def test_stop_scan_handler_does_not_cancel_when_unauthorized(
        self, mocker, emit
    ):
        mocker.patch.object(
            scan_module, "get_authenticated_user", AsyncMock(return_value=None)
        )
        get_jobs = mocker.patch.object(scan_module.high_prio_queue, "get_jobs")

        await stop_scan_handler("sid")

        get_jobs.assert_not_called()


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
