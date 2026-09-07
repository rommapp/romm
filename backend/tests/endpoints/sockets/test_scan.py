from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
import socketio
from rq.exceptions import AbandonedJobError, InvalidJobOperation
from rq.job import JobStatus
from tests.scan_job_stubs import (
    NON_SCAN_FUNC,
    make_job,
    make_scoped_job,
    make_task_job,
    patch_scan_jobs,
)

from endpoints.sockets import scan as scan_module
from endpoints.sockets.scan import (
    ScanStats,
    _identify_rom,
    _scan_selected_roms,
    _should_extract_title_ids,
    _should_hash_incrementally,
    _should_reparse_tags,
    reject_unauthorized_scan,
    scan_handler,
    scan_platforms,
    should_scan_rom,
    stop_scan_handler,
)
from exceptions.fs_exceptions import FolderStructureNotMatchException
from exceptions.socket_exceptions import ScanStoppedException
from handler.auth.constants import Scope
from handler.database.roms_handler import SyncedRomFiles
from handler.filesystem.roms_handler import (
    FSRom,
    FSRomsHandler,
    ParsedRomFiles,
    ParsedTags,
)
from handler.rom_files import RomFilesRefresh
from handler.scan_handler import MetadataSource, ScanType
from handler.scan_jobs import SCAN_PLATFORMS_FUNC
from models.firmware import Firmware
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory, RomIdentity
from utils.platform_slugs import UniversalPlatformSlug as UPS


@pytest.fixture
def hold_everything_back(mocker):
    """An interval no test can outrun, so coalescing is what decides."""
    mocker.patch.object(scan_module, "SCAN_STATS_PUBLISH_INTERVAL", 3600)


class TestScanStatsPublishing:
    """Counters are exact on every increment; only the reporting is coalesced."""

    @pytest.fixture
    def socket_manager(self, mocker):
        mocker.patch.object(scan_module, "update_job_meta")
        return AsyncMock()

    async def test_reports_once_for_a_burst_of_increments(
        self, hold_everything_back, socket_manager
    ):
        stats = ScanStats()

        for _ in range(50):
            await stats.increment(socket_manager=socket_manager, scanned_roms=1)

        # The first increment reports, the rest ride along with it.
        socket_manager.emit.assert_awaited_once()
        assert stats.scanned_roms == 50

    async def test_flush_reports_what_a_burst_held_back(
        self, hold_everything_back, socket_manager
    ):
        stats = ScanStats()
        for _ in range(5):
            await stats.increment(socket_manager=socket_manager, scanned_roms=1)
        socket_manager.emit.reset_mock()

        await stats.flush(socket_manager)

        assert socket_manager.emit.await_args.args[1]["scanned_roms"] == 5

    async def test_flush_is_quiet_with_nothing_held_back(self, mocker, socket_manager):
        mocker.patch.object(scan_module, "SCAN_STATS_PUBLISH_INTERVAL", 0)
        stats = ScanStats()
        await stats.increment(socket_manager=socket_manager, scanned_roms=1)
        socket_manager.emit.reset_mock()

        await stats.flush(socket_manager)

        socket_manager.emit.assert_not_awaited()

    async def test_a_phase_boundary_reports_immediately(
        self, hold_everything_back, socket_manager
    ):
        stats = ScanStats()
        await stats.increment(socket_manager=socket_manager, scanned_roms=1)
        socket_manager.emit.reset_mock()

        await stats.update(socket_manager=socket_manager, total_roms=12)

        assert socket_manager.emit.await_args.args[1]["total_roms"] == 12

    async def test_the_first_report_survives_a_clock_reading_near_zero(
        self, mocker, socket_manager
    ):
        # A monotonic clock counting from boot can read below the interval, and
        # the first report must not be coalesced against a scan that never ran.
        mocker.patch.object(scan_module.time, "monotonic", return_value=0.01)
        stats = ScanStats()

        await stats.increment(socket_manager=socket_manager, scanned_roms=1)

        socket_manager.emit.assert_awaited_once()


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


@pytest.fixture
def patched(mocker):
    """Patch the collaborators of scan_platforms so a scan can be driven whole."""
    socket_manager = AsyncMock()
    mocker.patch.object(scan_module, "_get_socket_manager", return_value=socket_manager)
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
    mocker.patch.object(scan_module.db_rom_handler, "invalidate_filter_values_cache")
    config = MagicMock()
    config.GAMELIST_AUTO_EXPORT_ON_SCAN = False
    config.PEGASUS_AUTO_EXPORT_ON_SCAN = False
    mocker.patch.object(scan_module.cm, "get_config", return_value=config)

    # Skip the actual per-platform scanning, returning the stats unchanged.
    async def fake_identify(**kwargs):
        return kwargs["scan_stats"]

    mocker.patch.object(scan_module, "_identify_platform", side_effect=fake_identify)
    return socket_manager


class TestScanFailureReporting:
    """A failed scan still reports the progress it made before saying it failed."""

    async def test_a_failure_publishes_what_an_increment_held_back(
        self, patched, hold_everything_back, mocker
    ):
        update_job_meta = mocker.patch.object(scan_module, "update_job_meta")

        async def scan_then_fail(**kwargs):
            await kwargs["scan_stats"].increment(
                socket_manager=kwargs["socket_manager"], scanned_roms=7
            )
            raise RuntimeError("boom")

        mocker.patch.object(
            scan_module, "_identify_platform", side_effect=scan_then_fail
        )

        with pytest.raises(RuntimeError):
            await scan_platforms(platform_ids=[], metadata_sources=[])

        assert update_job_meta.call_args.args[0]["scan_stats"]["scanned_roms"] == 7
        assert patched.emit.await_args.args[0] == "scan:done_ko"


class TestScanTotals:
    """The scan tracker totals must reflect the platforms/roms actually scanned."""

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

    async def test_scan_selected_filesystem_slug(self, patched, mocker):
        """A never-scanned folder can be targeted by its filesystem slug."""
        result = await scan_platforms(
            platform_ids=[],
            metadata_sources=[],
            scan_type=ScanType.QUICK,
            platform_fs_slugs=["new1"],
        )

        # Only the selected folder is scanned, not every filesystem platform.
        assert result.total_platforms == 1
        assert result.total_roms == 100


class TestScreenScraperScanReporting:
    """The scan hands ScreenScraper's own bookkeeping to ss_handler, and only
    when the scan actually uses ScreenScraper."""

    @pytest.fixture
    def patched(self, patched, mocker):
        """The shared harness, narrowed to a single platform with no roms."""
        mocker.patch.object(
            scan_module.fs_platform_handler,
            "get_platforms",
            AsyncMock(return_value=["genesis"]),
        )
        mocker.patch.object(
            scan_module.fs_rom_handler, "count_roms", AsyncMock(return_value=0)
        )
        mocker.patch.object(
            scan_module.db_platform_handler, "get_platforms", return_value=[]
        )
        return patched

    async def test_begins_a_screenscraper_scan(self, patched, mocker):
        begin = mocker.patch.object(
            scan_module, "begin_ss_scan", new=AsyncMock(return_value=None)
        )

        await scan_platforms(
            platform_ids=[],
            metadata_sources=[MetadataSource.SS],
            scan_type=ScanType.QUICK,
        )

        begin.assert_awaited_once()

    async def test_leaves_screenscraper_state_alone_when_it_is_not_used(
        self, patched, mocker
    ):
        """The state is process-global and DEV_MODE scans run in-process, so a
        scan without ScreenScraper must not clear an overlapping scan's limits
        and skipped ROMs."""
        begin = mocker.patch.object(
            scan_module, "begin_ss_scan", new=AsyncMock(return_value=None)
        )

        await scan_platforms(
            platform_ids=[],
            metadata_sources=[MetadataSource.IGDB],
            scan_type=ScanType.QUICK,
        )

        begin.assert_not_awaited()

    async def test_reports_the_screenscraper_summary_at_the_end(self, patched, mocker):
        mocker.patch.object(
            scan_module, "begin_ss_scan", new=AsyncMock(return_value=None)
        )
        summary = mocker.patch.object(scan_module, "log_ss_scan_summary")

        await scan_platforms(
            platform_ids=[],
            metadata_sources=[MetadataSource.SS],
            scan_type=ScanType.QUICK,
        )

        summary.assert_called_once()

    async def test_stays_quiet_when_screenscraper_is_not_used(self, patched, mocker):
        summary = mocker.patch.object(scan_module, "log_ss_scan_summary")

        await scan_platforms(
            platform_ids=[], metadata_sources=[], scan_type=ScanType.QUICK
        )

        summary.assert_not_called()


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
        """QUICK should scan an existing rom, to reconcile its files"""
        result = should_scan_rom(ScanType.QUICK, rom, [], ["igdb"])
        assert result is True

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
            (ScanType.QUICK, False, None, False, True),
            (ScanType.QUICK, True, True, False, True),
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


class TestShouldReparseTags:
    """Which scans re-read filename tags onto a row that already exists."""

    @pytest.fixture
    def rom(self) -> Rom:
        rom: Rom = Mock(spec=Rom)
        rom.id = 1
        return rom

    def test_complete_rescan_reparses(self, rom: Rom):
        assert _should_reparse_tags(ScanType.COMPLETE, rom, []) is True

    @pytest.mark.parametrize(
        "scan_type",
        [
            ScanType.QUICK,
            ScanType.NEW_PLATFORMS,
            ScanType.UPDATE,
            ScanType.UNMATCHED,
        ],
    )
    def test_other_scans_leave_tags_alone(self, scan_type, rom: Rom):
        assert _should_reparse_tags(scan_type, rom, []) is False

    def test_hashes_rescan_leaves_tags_alone(self, rom: Rom):
        """A hashes rescan is scoped to file bytes, so it must not touch tags."""
        assert _should_reparse_tags(ScanType.HASHES, rom, []) is False

    def test_selected_roms_reparse_under_any_scan_type(self, rom: Rom):
        assert _should_reparse_tags(ScanType.QUICK, rom, [rom.id]) is True
        assert _should_reparse_tags(ScanType.HASHES, rom, [rom.id]) is True

    def test_unselected_rom_is_left_alone(self, rom: Rom):
        assert _should_reparse_tags(ScanType.QUICK, rom, [rom.id + 99]) is False


class TestShouldExtractTitleIds:
    """Which rescans pay for another native parse of a rom's binaries."""

    @staticmethod
    def _rom(platform_slug: str, title_id: str | None) -> Rom:
        # Built untyped and cast, since `platform_slug` is a read-only property.
        rom = Mock(spec=Rom)
        rom.title_id = title_id
        rom.platform_slug = platform_slug
        return cast(Rom, rom)

    def test_a_stored_id_is_not_re_read(self):
        rom = self._rom("psp", "ULUS-10041")

        assert _should_extract_title_ids(ScanType.UPDATE, rom) is False
        assert _should_extract_title_ids(ScanType.UNMATCHED, rom) is False

    def test_a_rom_without_an_id_is_read(self):
        assert (
            _should_extract_title_ids(ScanType.UPDATE, self._rom("psp", None)) is True
        )

    @pytest.mark.parametrize("scan_type", [ScanType.COMPLETE, ScanType.HASHES])
    def test_a_rescan_that_re_reads_the_bytes_re_reads_the_id(
        self, scan_type: ScanType
    ):
        """Replacing a file in place would otherwise leave the old id beside the
        hashes of the new bytes."""
        rom = self._rom("psp", "ULUS-10041")

        assert _should_extract_title_ids(scan_type, rom) is True

    @pytest.mark.parametrize("platform_slug", ["switch", "switch-2"])
    def test_switch_always_re_reads(self, platform_slug: str):
        """The same parse settles the per-file categories, which a rebuild would
        otherwise take from the folder names instead."""
        rom = self._rom(platform_slug, "0100ABCD12340000")

        assert _should_extract_title_ids(ScanType.UPDATE, rom) is True


class TestIdentifyRomTagReparse:
    """A complete rescan re-reads filename tags onto an existing entry.

    Tags are parsed once at insert and otherwise never revisited, so a change to
    `parse_tags` (a new normalization rule, say) would never reach rows scanned
    before it. A HASHES scan is used for the negative case so the flow returns
    right after the file-rebuild step.
    """

    @pytest.fixture
    def patched(self, mocker):
        mocker.patch.object(
            scan_module, "redis_client", Mock(get=Mock(return_value=None))
        )

        fs = scan_module.fs_rom_handler
        mocker.patch.object(
            fs,
            "parse_tags",
            return_value=ParsedTags(
                version="1.1",
                revision="A",
                regions=["USA"],
                languages=["English"],
                other_tags=["Proto"],
            ),
        )
        mocker.patch.object(fs, "get_roms_fs_structure", return_value="test/roms")
        mocker.patch.object(fs, "get_file_name_with_no_tags", return_value="Game")
        mocker.patch.object(
            fs,
            "get_rom_files",
            AsyncMock(
                return_value=ParsedRomFiles(
                    rom_files=[],
                    crc_hash="crc",
                    md5_hash="md5",
                    sha1_hash="sha1",
                    ra_hash="",
                )
            ),
        )

        config = MagicMock()
        config.SKIP_HASH_CALCULATION = False
        mocker.patch.object(scan_module.cm, "get_config", return_value=config)

        scan_rom = mocker.patch.object(
            scan_module,
            "scan_rom",
            AsyncMock(return_value=MagicMock(is_identified=False)),
        )

        # A COMPLETE scan runs past the point a HASHES scan returns at, into the
        # resource downloads and the closing emit, none of which is under test.
        mocker.patch.object(scan_module, "download_rom_resources", new=AsyncMock())
        mocker.patch.object(scan_module, "SimpleRomSchema", MagicMock())

        db = mocker.patch.object(scan_module, "db_rom_handler")
        db.add_rom.return_value = MagicMock(
            is_identified=False,
            id=1,
            url_cover="",
            url_manual="",
            url_screenshots=[],
        )
        db.sync_rom_files.return_value = SyncedRomFiles(
            files=[], orphaned_cover_paths=[]
        )
        return SimpleNamespace(db=db, scan_rom=scan_rom)

    def _existing_rom(self) -> Rom:
        """A row carrying the raw values an older parser would have written."""
        rom = Rom(
            platform_id=1,
            fs_name="Game (USA) (En) (Proto) (v1.1) (Rev A).zip",
            fs_path="test/roms",
            regions=["us"],
            languages=["en"],
            tags=["proto"],
            revision="",
            version="",
        )
        rom.id = 1
        return rom

    async def _run(self, rom: Rom, scan_type: ScanType, roms_ids: list[int]):
        fs_rom: FSRom = {
            "fs_name": "Game (USA) (En) (Proto) (v1.1) (Rev A).zip",
            "flat": True,
            "nested": False,
            "files": [],
            "crc_hash": "",
            "md5_hash": "",
            "sha1_hash": "",
            "ra_hash": "",
        }
        platform = Platform(name="Test", slug="test", fs_slug="test")
        platform.id = 1

        await _identify_rom(
            platform=platform,
            fs_rom=fs_rom,
            rom=rom,
            scan_type=scan_type,
            roms_ids=roms_ids,
            metadata_sources=[],
            launchbox_remote_enabled=False,
            playmatch_enabled=False,
            socket_manager=AsyncMock(),
            scan_stats=AsyncMock(),
            scanned_rom_ids=set(),
        )

    async def test_complete_rescan_rewrites_stale_tags(self, patched):
        rom = self._existing_rom()

        await self._run(rom, ScanType.COMPLETE, [])

        # scan_rom carries these columns forward from the rom it is handed, and
        # merging its result is what persists them.
        assert rom.regions == ["USA"]
        assert rom.languages == ["English"]
        assert rom.tags == ["Proto"]
        assert rom.revision == "A"
        assert rom.version == "1.1"

        # The mutated instance is the one carried onward, not a copy.
        assert patched.scan_rom.call_args.kwargs["rom"] is rom

    async def test_hashes_rescan_keeps_existing_tags(self, patched):
        rom = self._existing_rom()

        await self._run(rom, ScanType.HASHES, [])

        assert rom.regions == ["us"]
        assert rom.languages == ["en"]
        assert rom.tags == ["proto"]

    async def test_selected_rom_rewrites_tags(self, patched):
        rom = self._existing_rom()

        await self._run(rom, ScanType.HASHES, [rom.id])

        assert rom.regions == ["USA"]
        assert rom.languages == ["English"]


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
        enqueue = mocker.patch.object(scan_module.scan_queue, "enqueue")
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
        queued_jobs = mocker.patch.object(scan_module, "get_queued_scan_jobs")

        await stop_scan_handler("sid")

        queued_jobs.assert_not_called()


def patch_identify_rom(
    mocker,
    *,
    parsed: ParsedRomFiles,
    roms_fs_structure: str,
    name_with_no_tags: str,
    platform_slug: str,
    embed_switch_title_ids: bool = False,
    renamed_rom_fs_name: str | None = None,
) -> tuple[Mock, Platform]:
    """Stub out everything `_identify_rom` reaches so only the wiring under test
    is exercised, returning the patched db handler and the platform to scan."""
    mocker.patch.object(scan_module, "redis_client", Mock(get=Mock(return_value=None)))

    fs = scan_module.fs_rom_handler
    mocker.patch.object(
        fs,
        "parse_tags",
        return_value=ParsedTags(
            version="", revision="", regions=[], languages=[], other_tags=[]
        ),
    )
    mocker.patch.object(fs, "get_roms_fs_structure", return_value=roms_fs_structure)
    mocker.patch.object(
        fs, "get_file_name_with_no_tags", return_value=name_with_no_tags
    )
    mocker.patch.object(fs, "get_rom_files", AsyncMock(return_value=parsed))
    mocker.patch.object(
        fs,
        "embed_switch_title_ids",
        AsyncMock(return_value=renamed_rom_fs_name),
    )

    config = MagicMock()
    config.SKIP_HASH_CALCULATION = False
    config.SKIP_TITLE_ID_EXTRACTION = False
    config.EMBED_SWITCH_TITLE_IDS = embed_switch_title_ids
    mocker.patch.object(scan_module.cm, "get_config", return_value=config)

    mocker.patch.object(
        scan_module, "scan_rom", AsyncMock(return_value=MagicMock(is_identified=False))
    )

    db = mocker.patch.object(scan_module, "db_rom_handler")
    db.add_rom.return_value = MagicMock(is_identified=False, id=99)

    platform = Platform(name=platform_slug, slug=platform_slug, fs_slug=platform_slug)
    platform.id = 1
    return db, platform


async def run_identify_rom(platform: Platform, fs_rom: FSRom) -> None:
    await _identify_rom(
        platform=platform,
        fs_rom=fs_rom,
        rom=None,
        scan_type=ScanType.HASHES,
        roms_ids=[],
        metadata_sources=[],
        launchbox_remote_enabled=False,
        playmatch_enabled=False,
        socket_manager=AsyncMock(),
        scan_stats=AsyncMock(),
        scanned_rom_ids=set(),
    )


def make_fs_rom(fs_name: str) -> FSRom:
    return {
        "fs_name": fs_name,
        "flat": True,
        "nested": False,
        "files": [],
        "crc_hash": "",
        "md5_hash": "",
        "sha1_hash": "",
        "ra_hash": "",
    }


class TestIdentifyRomReassociation:
    """`_identify_rom` reassociates a renamed/moved file with its missing entry.

    A HASHES scan is used so the flow returns right after the file-rebuild step,
    keeping the metadata/resource path out of scope for these wiring tests.
    """

    @pytest.fixture
    def patched(self, mocker):
        return patch_identify_rom(
            mocker,
            parsed=ParsedRomFiles(
                rom_files=[],
                crc_hash="crc",
                md5_hash="md5",
                sha1_hash="sha1",
                ra_hash="",
            ),
            roms_fs_structure="test/roms",
            name_with_no_tags="New Name",
            platform_slug="test",
        )

    async def _run(self, platform: Platform) -> None:
        await run_identify_rom(platform, make_fs_rom("New Name.zip"))

    async def test_reassociates_with_missing_entry(self, patched):
        db, platform = patched
        missing = MagicMock(id=42, name="Old Game", fs_name="old.zip")
        db.get_matching_missing_rom.return_value = missing
        db.update_rom.return_value = missing

        await self._run(platform)

        db.get_matching_missing_rom.assert_called_once_with(
            platform_id=1,
            crc_hash="crc",
            md5_hash="md5",
            sha1_hash="sha1",
            title_id=None,
        )
        db.update_rom.assert_called_once()
        rom_id, data = db.update_rom.call_args.args
        assert rom_id == 42
        assert data["missing_from_fs"] is False
        assert data["fs_name"] == "New Name.zip"
        # No brand-new row is inserted; add_rom only persists the scan result.
        assert db.add_rom.call_count == 1

    async def test_title_id_is_offered_when_the_platform_is_not_hashed(
        self, patched, mocker
    ):
        """Switch files carry no hashes, so the title id is the only identity.

        Without it a renamed Switch file lands as a duplicate and strands the
        original entry, along with its collections and notes, as missing.
        """
        db, platform = patched
        db.get_matching_missing_rom.return_value = None
        mocker.patch.object(
            scan_module.fs_rom_handler,
            "get_rom_files",
            AsyncMock(
                return_value=ParsedRomFiles(
                    rom_files=[],
                    crc_hash="",
                    md5_hash="",
                    sha1_hash="",
                    ra_hash="",
                    identity=RomIdentity(title_id="0100ABCD12340000"),
                )
            ),
        )

        await self._run(platform)

        db.get_matching_missing_rom.assert_called_once_with(
            platform_id=1,
            crc_hash="",
            md5_hash="",
            sha1_hash="",
            title_id="0100ABCD12340000",
        )

    async def test_files_are_reconciled_in_place(self, patched):
        db, platform = patched
        db.get_matching_missing_rom.return_value = None
        db.sync_rom_files.return_value = SyncedRomFiles(
            files=[], orphaned_cover_paths=[]
        )

        await self._run(platform)

        # Rows are reconciled against the scan, so file ids survive the rescan.
        db.sync_rom_files.assert_called_once_with(99, [])

    async def test_orphaned_soundtrack_covers_are_unlinked(self, patched, mocker):
        db, platform = patched
        db.get_matching_missing_rom.return_value = None
        db.sync_rom_files.return_value = SyncedRomFiles(
            files=[], orphaned_cover_paths=["covers/track01.png"]
        )
        remove = mocker.patch.object(scan_module, "remove_persisted_cover")

        await self._run(platform)

        remove.assert_called_once_with("covers/track01.png")

    async def test_creates_new_entry_when_no_match(self, patched):
        db, platform = patched
        db.get_matching_missing_rom.return_value = None

        await self._run(platform)

        db.get_matching_missing_rom.assert_called_once()
        # No reassociation update happens on the create path.
        db.update_rom.assert_not_called()
        # A new row is inserted, then the scan result is persisted (two calls).
        assert db.add_rom.call_count == 2
        created = db.add_rom.call_args_list[0].args[0]
        assert isinstance(created, Rom)
        assert created.fs_name == "New Name.zip"


class TestIdentifyRomTitleIdEmbedRename:
    """`_identify_rom` reconciles Rom.fs_name when a single-file Switch rom is
    renamed on disk to embed its title id."""

    NEW_NAME = "Game [0100ABCD12340000][v0].nsp"

    @pytest.fixture
    def patched(self, mocker):
        db, platform = patch_identify_rom(
            mocker,
            parsed=ParsedRomFiles(
                rom_files=[],
                crc_hash="crc",
                md5_hash="md5",
                sha1_hash="sha1",
                ra_hash="",
                identity=RomIdentity(title_id="0100ABCD12340000"),
            ),
            roms_fs_structure="switch/roms",
            name_with_no_tags="Game",
            platform_slug="switch",
            embed_switch_title_ids=True,
            renamed_rom_fs_name=self.NEW_NAME,
        )
        db.get_matching_missing_rom.return_value = None
        return db, platform

    async def test_new_entry_carries_embedded_name(self, patched):
        db, platform = patched
        fs_rom = make_fs_rom("Game.nsp")

        await run_identify_rom(platform, fs_rom)

        # The initial insert carries the renamed on-disk name, and the shared
        # fs_rom dict is updated so scan_rom persists the same name.
        created = db.add_rom.call_args_list[0].args[0]
        assert created.fs_name == self.NEW_NAME
        assert fs_rom["fs_name"] == self.NEW_NAME


class TestIdentifyRomPersistsFileCategory:
    """A file losing its category before `sync_rom_files` persists an update as
    a plain game."""

    UPDATE_TITLE_ID = "0100F4700B2E0800"

    @pytest.fixture
    def patched(self, mocker):
        update_file = RomFile(
            file_name="Game [UPD][v655360].nsp",
            file_path="switch/roms",
            file_size_bytes=1024,
            category=RomFileCategory.UPDATE,
        )
        db, platform = patch_identify_rom(
            mocker,
            parsed=ParsedRomFiles(
                rom_files=[update_file],
                crc_hash="crc",
                md5_hash="md5",
                sha1_hash="sha1",
                ra_hash="",
                identity=RomIdentity(title_id=self.UPDATE_TITLE_ID),
            ),
            roms_fs_structure="switch/roms",
            name_with_no_tags="Game",
            platform_slug="switch",
        )
        # The persist loop calls this per saved file; keep it inert.
        mocker.patch.object(scan_module, "persist_soundtrack_cover")
        db.get_matching_missing_rom.return_value = None
        db.sync_rom_files.side_effect = lambda rom_id, files: SyncedRomFiles(
            files=list(files), orphaned_cover_paths=[]
        )
        return db, platform

    async def test_rebuilt_file_keeps_category(self, patched):
        db, platform = patched

        await run_identify_rom(platform, make_fs_rom("Game.nsp"))

        db.sync_rom_files.assert_called_once()
        rom_id, synced_files = db.sync_rom_files.call_args.args
        assert rom_id == 99
        assert len(synced_files) == 1
        persisted = synced_files[0]
        assert isinstance(persisted, RomFile)
        assert persisted.category == RomFileCategory.UPDATE


class TestIdentifyPlatformMarksMissingBeforeScan:
    """`_identify_platform` must flag missing entries before identifying files.

    Reassociation matches a renamed/moved file against entries already flagged
    `missing_from_fs`. That flag is only accurate if it is synced before the
    identify loop runs, so a single rename+scan can reassociate instead of
    creating a duplicate.
    """

    async def test_mark_missing_runs_before_identify(self, mocker):
        calls: list[str] = []

        mocker.patch.object(
            scan_module, "redis_client", Mock(get=Mock(return_value=None))
        )

        platform = Platform(name="Test", slug="test", fs_slug="test")
        platform.id = 1
        platform.missing_from_fs = False
        db_platform = mocker.patch.object(scan_module, "db_platform_handler")
        db_platform.get_platform_by_fs_slug.return_value = platform
        db_platform.add_platform.return_value = platform

        mocker.patch.object(
            scan_module, "scan_platform", AsyncMock(return_value=platform)
        )
        # The scanning_platform emit serializes the platform; stub it out.
        mocker.patch.object(
            scan_module.PlatformSchema,
            "model_validate",
            return_value=Mock(model_dump=Mock(return_value={})),
        )
        mocker.patch.object(
            scan_module.fs_firmware_handler,
            "get_firmware",
            AsyncMock(return_value=[]),
        )
        fs_rom: FSRom = {
            "fs_name": "New Name.zip",
            "flat": True,
            "nested": False,
            "files": [],
            "crc_hash": "",
            "md5_hash": "",
            "sha1_hash": "",
            "ra_hash": "",
        }
        mocker.patch.object(
            scan_module.fs_rom_handler, "get_roms", AsyncMock(return_value=[fs_rom])
        )

        def record_mark_missing(*args, **kwargs):
            calls.append("mark_missing")
            return []

        db_rom = mocker.patch.object(scan_module, "db_rom_handler")
        db_rom.get_roms_by_fs_name.return_value = {}
        db_rom.mark_missing_roms.side_effect = record_mark_missing
        db_firmware = mocker.patch.object(scan_module, "db_firmware_handler")
        db_firmware.mark_missing_firmware.return_value = []

        async def fake_identify(**kwargs):
            calls.append("identify")

        mocker.patch.object(scan_module, "_identify_rom", side_effect=fake_identify)

        await scan_module._identify_platform(
            platform_slug="test",
            scan_type=ScanType.QUICK,
            fs_platforms=["test"],
            roms_ids=[],
            metadata_sources=[],
            launchbox_remote_enabled=False,
            playmatch_enabled=False,
            socket_manager=AsyncMock(),
            scan_stats=AsyncMock(),
            scanned_rom_ids=set(),
        )

        assert "mark_missing" in calls and "identify" in calls
        assert calls.index("mark_missing") < calls.index("identify")


class TestIdentifyPlatformEmitsRestoredRoms:
    """A platform scan tells the client about ROMs that came back.

    An update scan skips the entries it does not match, so nothing else in the
    loop emits for them and an open gallery would keep showing a stale
    "missing" badge until a refetch.
    """

    @pytest.fixture
    def patched(self, mocker):
        mocker.patch.object(
            scan_module, "redis_client", Mock(get=Mock(return_value=None))
        )

        platform = Platform(name="Test", slug="test", fs_slug="test")
        platform.id = 1
        platform.missing_from_fs = False
        db_platform = mocker.patch.object(scan_module, "db_platform_handler")
        db_platform.get_platform_by_fs_slug.return_value = platform
        db_platform.add_platform.return_value = platform

        mocker.patch.object(
            scan_module, "scan_platform", AsyncMock(return_value=platform)
        )
        mocker.patch.object(
            scan_module.PlatformSchema,
            "model_validate",
            return_value=Mock(model_dump=Mock(return_value={})),
        )
        mocker.patch.object(
            scan_module.fs_firmware_handler,
            "get_firmware",
            AsyncMock(return_value=[]),
        )

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
        mocker.patch.object(
            scan_module.fs_rom_handler, "get_roms", AsyncMock(return_value=[fs_rom])
        )

        rom = Rom(fs_name="Game.zip", platform_id=platform.id)
        rom.id = 42

        db_rom = mocker.patch.object(scan_module, "db_rom_handler")
        db_rom.get_roms_by_fs_name.return_value = {"Game.zip": rom}
        db_rom.mark_missing_roms.return_value = []
        db_rom.get_rom.return_value = rom

        db_firmware = mocker.patch.object(scan_module, "db_firmware_handler")
        db_firmware.mark_missing_firmware.return_value = []

        mocker.patch.object(
            scan_module.SimpleRomSchema,
            "from_orm_with_factory",
            return_value=Mock(model_dump=Mock(return_value={"id": rom.id})),
        )
        mocker.patch.object(scan_module, "_identify_rom", AsyncMock())

        return db_rom

    async def _run(self, socket_manager, scan_type=ScanType.UPDATE):
        await scan_module._identify_platform(
            platform_slug="test",
            scan_type=scan_type,
            fs_platforms=["test"],
            roms_ids=[],
            metadata_sources=[],
            launchbox_remote_enabled=False,
            playmatch_enabled=False,
            socket_manager=socket_manager,
            scan_stats=AsyncMock(),
            scanned_rom_ids=set(),
        )

    async def test_emits_for_rom_that_is_no_longer_missing(self, patched):
        patched.get_missing_rom_ids.return_value = {42}
        socket_manager = AsyncMock()

        await self._run(socket_manager)

        patched.bulk_mark_present.assert_called_once_with(1, [42])
        patched.get_rom_simple.assert_called_once_with(42)
        assert any(
            call.args[0] == "scan:scanning_rom"
            for call in socket_manager.emit.call_args_list
        )

    async def test_emits_for_a_restored_rom_the_scan_visits(self, patched):
        patched.get_missing_rom_ids.return_value = {42}
        socket_manager = AsyncMock()

        await self._run(socket_manager, scan_type=ScanType.QUICK)

        patched.bulk_mark_present.assert_not_called()
        assert any(
            call.args[0] == "scan:scanning_rom"
            for call in socket_manager.emit.call_args_list
        )

    async def test_no_emit_for_rom_that_was_already_present(self, patched):
        patched.get_missing_rom_ids.return_value = set()
        socket_manager = AsyncMock()

        await self._run(socket_manager)

        patched.get_rom_simple.assert_not_called()
        assert not any(
            call.args[0] == "scan:scanning_rom"
            for call in socket_manager.emit.call_args_list
        )


class TestIdentifyPlatformFirmwareReporting:
    """The platform emit reports firmware discovered by this scan only.

    Reporting the platform's total firmware count made every re-scan look like
    it had found new firmware.
    """

    @pytest.fixture
    def patched(self, mocker):
        mocker.patch.object(
            scan_module, "redis_client", Mock(get=Mock(return_value=None))
        )

        platform = Platform(name="Test", slug="test", fs_slug="test")
        platform.id = 1
        platform.missing_from_fs = False
        db_platform = mocker.patch.object(scan_module, "db_platform_handler")
        db_platform.get_platform_by_fs_slug.return_value = platform
        db_platform.add_platform.return_value = platform

        mocker.patch.object(
            scan_module, "scan_platform", AsyncMock(return_value=platform)
        )
        mocker.patch.object(
            scan_module.PlatformSchema,
            "model_validate",
            return_value=Mock(model_dump=Mock(return_value={"id": platform.id})),
        )
        mocker.patch.object(
            scan_module.fs_firmware_handler,
            "get_firmware",
            AsyncMock(return_value=["known.bin", "brand-new.bin"]),
        )
        mocker.patch.object(
            scan_module,
            "scan_firmware",
            AsyncMock(return_value=Firmware(file_name="known.bin", platform_id=1)),
        )
        mocker.patch.object(
            scan_module.Firmware, "verify_file_hashes", return_value=True
        )
        mocker.patch.object(
            scan_module.fs_rom_handler, "get_roms", AsyncMock(return_value=[])
        )

        db_rom = mocker.patch.object(scan_module, "db_rom_handler")
        db_rom.get_roms_by_fs_name.return_value = {}
        db_rom.mark_missing_roms.return_value = []
        db_rom.get_missing_rom_ids.return_value = set()

        db_firmware = mocker.patch.object(scan_module, "db_firmware_handler")
        db_firmware.mark_missing_firmware.return_value = []
        # Only "brand-new.bin" is missing from the database.
        db_firmware.get_firmware_by_filename.side_effect = (
            lambda platform_id, file_name: (
                Firmware(file_name=file_name, platform_id=platform_id)
                if file_name == "known.bin"
                else None
            )
        )
        return db_firmware

    async def _emitted_platform_payload(self, socket_manager):
        await scan_module._identify_platform(
            platform_slug="test",
            scan_type=ScanType.QUICK,
            fs_platforms=["test"],
            roms_ids=[],
            metadata_sources=[],
            launchbox_remote_enabled=False,
            playmatch_enabled=False,
            socket_manager=socket_manager,
            scan_stats=AsyncMock(),
            scanned_rom_ids=set(),
        )
        return next(
            call.args[1]
            for call in socket_manager.emit.call_args_list
            if call.args[0] == "scan:scanning_platform"
        )

    async def test_counts_only_firmware_missing_from_the_database(self, patched):
        payload = await self._emitted_platform_payload(AsyncMock())

        assert payload["new_firmware_count"] == 1
        assert "firmware_count" not in payload

    async def test_reports_zero_when_all_firmware_is_already_known(self, patched):
        patched.get_firmware_by_filename.side_effect = (
            lambda platform_id, file_name: Firmware(
                file_name=file_name, platform_id=platform_id
            )
        )

        payload = await self._emitted_platform_payload(AsyncMock())

        assert payload["new_firmware_count"] == 0


class TestShouldHashFirmware:
    """The firmware counterpart of `_should_get_rom_files`."""

    def _stored(self, md5: str = "d41d8cd9") -> Firmware:
        firmware = Firmware(file_name="bios.bin", platform_id=1)
        firmware.md5_hash = md5
        return firmware

    @pytest.mark.parametrize("scan_type", [ScanType.COMPLETE, ScanType.HASHES])
    def test_hashes_when_the_scan_asked_for_hashes(self, scan_type):
        assert scan_module._should_hash_firmware(scan_type, self._stored()) is True

    @pytest.mark.parametrize(
        "scan_type",
        [
            ScanType.QUICK,
            ScanType.NEW_PLATFORMS,
            ScanType.UPDATE,
            ScanType.UNMATCHED,
        ],
    )
    def test_skips_a_known_entry_on_every_other_scan(self, scan_type):
        assert scan_module._should_hash_firmware(scan_type, self._stored()) is False

    def test_hashes_an_entry_missing_from_the_database(self):
        assert scan_module._should_hash_firmware(ScanType.QUICK, None) is True

    def test_hashes_an_entry_with_no_stored_hash(self):
        assert (
            scan_module._should_hash_firmware(ScanType.QUICK, self._stored(md5=""))
            is True
        )


class TestIdentifyFirmwareRehashing:
    """Firmware follows the same re-read rule as ROM files.

    `_should_get_rom_files` only re-reads a file's bytes for a new entry or a
    COMPLETE/HASHES scan. Firmware had no such gate, so a scan of any type
    re-hashed every BIOS file on the platform.
    """

    @pytest.fixture
    def patched(self, mocker):
        mocker.patch.object(
            scan_module, "redis_client", Mock(get=Mock(return_value=None))
        )
        mocker.patch.object(
            scan_module.Firmware, "verify_file_hashes", return_value=True
        )

        patches = SimpleNamespace(
            scan_firmware=mocker.patch.object(
                scan_module,
                "scan_firmware",
                AsyncMock(return_value=Firmware(file_name="bios.bin", platform_id=1)),
            ),
            get_file_size=mocker.patch.object(
                scan_module.fs_firmware_handler,
                "get_file_size",
                AsyncMock(return_value=1024),
            ),
            get_fs_structure=mocker.patch.object(
                scan_module.fs_firmware_handler,
                "get_firmware_fs_structure",
                return_value="bios/test",
            ),
            db_firmware=mocker.patch.object(scan_module, "db_firmware_handler"),
        )
        patches.db_firmware.get_firmware_by_filename.return_value = self._stored()
        return patches

    def _stored(
        self,
        *,
        size: int = 1024,
        md5: str = "d41d8cd9",
        missing=False,
        file_path: str = "bios/test",
    ):
        firmware = Firmware(file_name="bios.bin", file_path=file_path, platform_id=1)
        firmware.id = 7
        firmware.md5_hash = md5
        firmware.file_size_bytes = size
        firmware.missing_from_fs = missing
        return firmware

    async def _run(self, scan_type: ScanType = ScanType.QUICK) -> int:
        platform = Platform(name="Test", slug="test", fs_slug="test")
        platform.id = 1
        return await scan_module._identify_firmware(
            platform=platform, fs_fw="bios.bin", scan_type=scan_type
        )

    @pytest.mark.parametrize(
        "scan_type",
        [
            ScanType.QUICK,
            ScanType.NEW_PLATFORMS,
            ScanType.UPDATE,
            ScanType.UNMATCHED,
        ],
    )
    async def test_skips_rehashing_an_unchanged_file(self, patched, scan_type):
        assert await self._run(scan_type) == 0

        patched.scan_firmware.assert_not_called()
        patched.db_firmware.add_firmware.assert_not_called()

    @pytest.mark.parametrize("scan_type", [ScanType.COMPLETE, ScanType.HASHES])
    async def test_rehashes_when_the_scan_asked_for_hashes(self, patched, scan_type):
        await self._run(scan_type)

        patched.scan_firmware.assert_called_once()

    async def test_rehashes_when_the_file_size_changed(self, patched):
        patched.get_file_size.return_value = 2048

        await self._run()

        patched.scan_firmware.assert_called_once()

    async def test_rehashes_an_entry_with_no_stored_hash(self, patched):
        patched.db_firmware.get_firmware_by_filename.return_value = self._stored(md5="")

        await self._run()

        patched.scan_firmware.assert_called_once()
        # The database row already rules out a skip, so the file is never stat'd.
        patched.get_file_size.assert_not_called()

    async def test_hashes_firmware_missing_from_the_database(self, patched):
        patched.db_firmware.get_firmware_by_filename.return_value = None

        assert await self._run() == 1

        patched.scan_firmware.assert_called_once()

    async def test_clears_the_missing_flag_without_rehashing(self, patched):
        patched.db_firmware.get_firmware_by_filename.return_value = self._stored(
            missing=True
        )

        await self._run()

        patched.scan_firmware.assert_not_called()
        patched.db_firmware.update_firmware.assert_called_once_with(
            7, {"missing_from_fs": False}
        )

    async def test_leaves_an_unchanged_row_untouched(self, patched):
        await self._run()

        patched.db_firmware.update_firmware.assert_not_called()

    async def test_stats_the_file_where_it_was_enumerated(self, patched):
        await self._run()

        patched.get_file_size.assert_awaited_once_with("bios/test/bios.bin")

    async def test_rebuilds_a_row_recorded_at_a_stale_path(self, patched):
        """A library layout change leaves the recorded path pointing nowhere.

        Statting it would raise FileNotFoundError out of the whole scan, so a
        row whose path no longer matches is rehashed, which refreshes it.
        """
        patched.db_firmware.get_firmware_by_filename.return_value = self._stored(
            file_path="test/bios"
        )

        await self._run()

        patched.scan_firmware.assert_called_once()
        patched.get_file_size.assert_not_called()


class TestScanSelectedRoms:
    """A ROM-id-scoped scan works off the database, not the platform folder."""

    @pytest.fixture
    def platform(self):
        platform = Platform(name="Test", slug="test", fs_slug="test")
        platform.id = 1
        return platform

    @pytest.fixture
    def rom(self, platform):
        rom = Rom(fs_name="Game.zip", fs_path="roms/test", platform_id=platform.id)
        rom.id = 7
        return rom

    async def test_scans_the_selected_rom_without_listing_the_platform(
        self, mocker, platform, rom
    ):
        mocker.patch.object(
            scan_module, "redis_client", Mock(get=Mock(return_value=None))
        )
        mocker.patch.object(
            scan_module.fs_rom_handler, "file_exists", AsyncMock(return_value=True)
        )
        get_roms = mocker.patch.object(
            scan_module.fs_rom_handler, "get_roms", AsyncMock(return_value=[])
        )
        get_firmware = mocker.patch.object(
            scan_module.fs_firmware_handler, "get_firmware", AsyncMock(return_value=[])
        )
        db_rom = mocker.patch.object(scan_module, "db_rom_handler")
        identify = mocker.patch.object(
            scan_module, "_identify_rom", side_effect=AsyncMock()
        )

        await _scan_selected_roms(
            platform=platform,
            roms=[rom],
            scan_type=ScanType.COMPLETE,
            roms_ids=[rom.id],
            metadata_sources=[],
            launchbox_remote_enabled=False,
            playmatch_enabled=False,
            socket_manager=AsyncMock(),
            scan_stats=AsyncMock(),
            scanned_rom_ids=set(),
        )

        identify.assert_called_once()
        assert identify.call_args.kwargs["rom"] is rom
        assert identify.call_args.kwargs["fs_rom"]["fs_name"] == "Game.zip"

        # None of the platform-wide reconciliation a library scan does applies.
        get_roms.assert_not_called()
        get_firmware.assert_not_called()
        db_rom.mark_missing_roms.assert_not_called()
        db_rom.get_missing_rom_ids.assert_not_called()
        db_rom.bulk_mark_present.assert_not_called()

    async def test_a_rom_whose_file_is_gone_is_marked_missing_not_scanned(
        self, mocker, platform, rom
    ):
        """A library scan never reaches a missing entry, since it walks the
        filesystem. Scanning one here would clear its missing flag."""
        mocker.patch.object(
            scan_module, "redis_client", Mock(get=Mock(return_value=None))
        )
        mocker.patch.object(
            scan_module.fs_rom_handler, "file_exists", AsyncMock(return_value=False)
        )
        mocker.patch.object(
            scan_module.fs_rom_handler,
            "directory_exists",
            AsyncMock(return_value=False),
        )
        db_rom = mocker.patch.object(scan_module, "db_rom_handler")
        identify = mocker.patch.object(
            scan_module, "_identify_rom", side_effect=AsyncMock()
        )

        await _scan_selected_roms(
            platform=platform,
            roms=[rom],
            scan_type=ScanType.COMPLETE,
            roms_ids=[rom.id],
            metadata_sources=[],
            launchbox_remote_enabled=False,
            playmatch_enabled=False,
            socket_manager=AsyncMock(),
            scan_stats=AsyncMock(),
            scanned_rom_ids=set(),
        )

        identify.assert_not_called()
        db_rom.update_rom.assert_called_once_with(rom.id, {"missing_from_fs": True})

    async def test_a_multi_file_rom_is_reported_as_nested(self, mocker, platform, rom):
        mocker.patch.object(
            scan_module, "redis_client", Mock(get=Mock(return_value=None))
        )
        mocker.patch.object(
            scan_module.fs_rom_handler, "file_exists", AsyncMock(return_value=False)
        )
        mocker.patch.object(
            scan_module.fs_rom_handler,
            "directory_exists",
            AsyncMock(return_value=True),
        )
        mocker.patch.object(scan_module, "db_rom_handler")
        identify = mocker.patch.object(
            scan_module, "_identify_rom", side_effect=AsyncMock()
        )

        await _scan_selected_roms(
            platform=platform,
            roms=[rom],
            scan_type=ScanType.COMPLETE,
            roms_ids=[rom.id],
            metadata_sources=[],
            launchbox_remote_enabled=False,
            playmatch_enabled=False,
            socket_manager=AsyncMock(),
            scan_stats=AsyncMock(),
            scanned_rom_ids=set(),
        )

        fs_rom = identify.call_args.kwargs["fs_rom"]
        assert fs_rom["nested"] is True
        assert fs_rom["flat"] is False

    async def test_a_scan_stopped_mid_flight_raises(self, mocker, platform, rom):
        """`_identify_rom` returns rather than raises on the stop flag, so a stop
        that lands after the run started has to be re-checked here or the scan
        falls through to its post-scan work and reports itself done."""
        # Unset when _scan_selected_roms starts, set by the time it finishes.
        mocker.patch.object(
            scan_module, "redis_client", Mock(get=Mock(side_effect=[None, "1"]))
        )
        mocker.patch.object(
            scan_module.fs_rom_handler, "file_exists", AsyncMock(return_value=True)
        )
        mocker.patch.object(scan_module, "db_rom_handler")
        mocker.patch.object(scan_module, "_identify_rom", side_effect=AsyncMock())

        with pytest.raises(ScanStoppedException):
            await _scan_selected_roms(
                platform=platform,
                roms=[rom],
                scan_type=ScanType.COMPLETE,
                roms_ids=[rom.id],
                metadata_sources=[],
                launchbox_remote_enabled=False,
                playmatch_enabled=False,
                socket_manager=AsyncMock(),
                scan_stats=AsyncMock(),
                scanned_rom_ids=set(),
            )


class TestScopedScanSkipsLibraryWork:
    """`scan_platforms` with `roms_ids` must not fall into the library pipeline."""

    @pytest.fixture
    def patched(self, mocker):
        mocker.patch.object(
            scan_module, "_get_socket_manager", return_value=AsyncMock()
        )
        mocker.patch.object(scan_module.meta_gamelist_handler, "clear_cache")
        mocker.patch.object(
            scan_module.db_rom_handler, "invalidate_filter_values_cache"
        )
        config = MagicMock()
        config.GAMELIST_AUTO_EXPORT_ON_SCAN = False
        config.PEGASUS_AUTO_EXPORT_ON_SCAN = False
        mocker.patch.object(scan_module.cm, "get_config", return_value=config)

        platform = MagicMock(id=1, fs_slug="test")
        mocker.patch.object(
            scan_module.db_platform_handler, "get_platforms", return_value=[platform]
        )

        rom = MagicMock(id=7, platform_id=1)
        mocker.patch.object(
            scan_module.db_rom_handler, "get_roms_by_ids", return_value=[rom]
        )

        async def fake_scoped(**kwargs):
            return kwargs["scan_stats"]

        return {
            "scoped": mocker.patch.object(
                scan_module, "_scan_selected_roms", side_effect=fake_scoped
            ),
            "identify_platform": mocker.patch.object(
                scan_module, "_identify_platform", side_effect=AsyncMock()
            ),
            "get_platforms": mocker.patch.object(
                scan_module.fs_platform_handler, "get_platforms", AsyncMock()
            ),
            "count_roms": mocker.patch.object(
                scan_module.fs_rom_handler, "count_roms", AsyncMock(return_value=100)
            ),
            "mark_missing_platforms": mocker.patch.object(
                scan_module.db_platform_handler,
                "mark_missing_platforms",
                return_value=[],
            ),
            "refresh_all": mocker.patch.object(
                scan_module.db_collection_handler, "refresh_smart_collections"
            ),
            "refresh_scoped": mocker.patch.object(
                scan_module.db_collection_handler, "refresh_smart_collections_for_roms"
            ),
        }

    async def test_platform_pipeline_is_skipped(self, patched):
        result = await scan_platforms(
            platform_ids=[1],
            metadata_sources=[],
            scan_type=ScanType.COMPLETE,
            roms_ids=[7],
        )

        patched["scoped"].assert_called_once()
        patched["identify_platform"].assert_not_called()
        patched["get_platforms"].assert_not_called()
        patched["count_roms"].assert_not_called()
        patched["mark_missing_platforms"].assert_not_called()

        # Totals come from the selection, not from counting the platform folder.
        assert result.total_platforms == 1
        assert result.total_roms == 1

    async def test_totals_exclude_roms_whose_platform_is_gone(self, patched, mocker):
        """A rom whose platform row vanished can't be scanned, so counting it
        would leave the tracker short of its own total forever."""
        mocker.patch.object(
            scan_module.db_rom_handler,
            "get_roms_by_ids",
            return_value=[
                MagicMock(id=7, platform_id=1),
                MagicMock(id=8, platform_id=99),
            ],
        )

        result = await scan_platforms(
            platform_ids=[1],
            metadata_sources=[],
            scan_type=ScanType.COMPLETE,
            roms_ids=[7, 8],
        )

        # Only platform 1 exists, so only its rom is counted and scanned.
        assert result.total_platforms == 1
        assert result.total_roms == 1
        patched["scoped"].assert_called_once()
        assert [r.id for r in patched["scoped"].call_args.kwargs["roms"]] == [7]

    async def test_only_the_selected_roms_smart_collections_are_recounted(
        self, patched
    ):
        await scan_platforms(
            platform_ids=[1],
            metadata_sources=[],
            scan_type=ScanType.COMPLETE,
            roms_ids=[7],
        )

        patched["refresh_scoped"].assert_called_once_with([7])
        patched["refresh_all"].assert_not_called()

    async def test_a_library_scan_still_recounts_everything(self, patched, mocker):
        mocker.patch.object(
            scan_module.fs_platform_handler,
            "get_platforms",
            AsyncMock(return_value=["test"]),
        )

        await scan_platforms(
            platform_ids=[],
            metadata_sources=[],
            scan_type=ScanType.COMPLETE,
        )

        patched["refresh_all"].assert_called_once()
        patched["refresh_scoped"].assert_not_called()


class TestPostScanRecommendations:
    """Games scanned today get their edges now, not at the next nightly build."""

    async def test_the_scan_hands_over_the_roms_it_wrote(self, patched, mocker):
        top_up = mocker.patch.object(scan_module, "top_up_similarity")

        async def scan_two_roms(**kwargs):
            kwargs["scanned_rom_ids"].update({11, 12})
            return kwargs["scan_stats"]

        mocker.patch.object(
            scan_module, "_identify_platform", side_effect=scan_two_roms
        )

        await scan_platforms(platform_ids=[], metadata_sources=[])

        top_up.assert_called_once_with({11, 12})

    async def test_a_scan_that_wrote_nothing_still_calls_through(self, patched, mocker):
        """The empty case is the indexer's to short-circuit, not the scan's."""
        top_up = mocker.patch.object(scan_module, "top_up_similarity")

        await scan_platforms(platform_ids=[], metadata_sources=[])

        top_up.assert_called_once_with(set())

    async def test_a_failure_to_index_does_not_fail_the_scan(self, patched, mocker):
        mocker.patch.object(
            scan_module, "top_up_similarity", side_effect=RuntimeError("boom")
        )

        await scan_platforms(platform_ids=[], metadata_sources=[])

        assert patched.emit.await_args.args[0] == "scan:done"


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


class TestScanConcurrency:
    """A scan already in flight must block another from being enqueued."""

    @pytest.fixture
    def emit(self, mocker):
        emit = AsyncMock()
        mocker.patch.object(scan_module.socket_handler.socket_server, "emit", emit)
        return emit

    @pytest.fixture(autouse=True)
    def authorized(self, mocker):
        user = MagicMock()
        user.oauth_scopes = [Scope.TASKS_RUN]
        mocker.patch.object(
            scan_module, "get_authenticated_user", AsyncMock(return_value=user)
        )
        mocker.patch.object(scan_module, "DEV_MODE", False)

    async def test_enqueues_on_the_scan_queue_when_nothing_running(self, mocker, emit):
        # The scan queue has a worker of its own, so a scan cannot sit behind a
        # cleanup, nor hold one up for hours.
        patch_scan_jobs(mocker)
        enqueue = mocker.patch.object(scan_module.scan_queue, "enqueue")

        await scan_handler("sid", {"type": "quick"})

        enqueue.assert_called_once()

    async def test_refuses_when_a_scan_is_running(self, mocker, emit):
        patch_scan_jobs(mocker, running=make_job(SCAN_PLATFORMS_FUNC))
        enqueue = mocker.patch.object(scan_module.scan_queue, "enqueue")

        await scan_handler("sid", {"type": "quick"})

        enqueue.assert_not_called()
        emit.assert_awaited_once()
        assert emit.await_args.args[0] == "scan:done_ko"

    async def test_refuses_when_a_scan_is_queued(self, mocker, emit):
        patch_scan_jobs(mocker, scan_queued=[make_job(SCAN_PLATFORMS_FUNC)])
        enqueue = mocker.patch.object(scan_module.scan_queue, "enqueue")

        await scan_handler("sid", {"type": "quick"})

        enqueue.assert_not_called()

    async def test_a_scheduled_watcher_scan_does_not_block(self, mocker, emit):
        # A delayed watcher scan only moves when the scheduler releases it, so
        # a scheduler that is down would refuse manual scans for good.
        patch_scan_jobs(
            mocker,
            scheduled=[make_job(SCAN_PLATFORMS_FUNC, status=JobStatus.SCHEDULED)],
        )
        enqueue = mocker.patch.object(scan_module.scan_queue, "enqueue")

        await scan_handler("sid", {"type": "quick"})

        enqueue.assert_called_once()

    @pytest.mark.parametrize("queue", ["high_queued", "low_queued"])
    async def test_a_scan_left_on_an_older_queue_still_blocks(
        self, mocker, emit, queue
    ):
        # A scan enqueued by an older release sits on one of the other queues,
        # where a worker will still run it.
        patch_scan_jobs(mocker, **{queue: [make_job(SCAN_PLATFORMS_FUNC)]})
        enqueue = mocker.patch.object(scan_module.scan_queue, "enqueue")

        await scan_handler("sid", {"type": "quick"})

        enqueue.assert_not_called()

    async def test_a_cancelled_queued_scan_does_not_block(self, mocker, emit):
        patch_scan_jobs(
            mocker,
            scan_queued=[make_job(SCAN_PLATFORMS_FUNC, status=JobStatus.CANCELED)],
        )
        enqueue = mocker.patch.object(scan_module.scan_queue, "enqueue")

        await scan_handler("sid", {"type": "quick"})

        enqueue.assert_called_once()

    async def test_a_queued_scan_whose_status_is_gone_does_not_block(
        self, mocker, emit
    ):
        # RQ raises rather than reporting a status once the job hash expires.
        job = make_job(SCAN_PLATFORMS_FUNC)
        job.get_status.side_effect = InvalidJobOperation
        patch_scan_jobs(mocker, scan_queued=[job])
        enqueue = mocker.patch.object(scan_module.scan_queue, "enqueue")

        await scan_handler("sid", {"type": "quick"})

        enqueue.assert_called_once()

    async def test_a_worker_holding_a_job_that_is_gone_does_not_block(
        self, mocker, emit
    ):
        patch_scan_jobs(mocker, worker_lost=True)
        enqueue = mocker.patch.object(scan_module.scan_queue, "enqueue")

        await scan_handler("sid", {"type": "quick"})

        enqueue.assert_called_once()

    async def test_refusal_names_the_scan_in_the_way(self, mocker, emit):
        patch_scan_jobs(
            mocker,
            running=make_job(
                SCAN_PLATFORMS_FUNC, status=JobStatus.STARTED, task_name="Quick Scan"
            ),
        )
        mocker.patch.object(scan_module.scan_queue, "enqueue")

        await scan_handler("sid", {"type": "quick"})

        assert emit.await_args.args[1] == "Quick Scan is already running"

    async def test_refusal_says_a_stopping_scan_is_worth_retrying(self, mocker, emit):
        # A stopped scan holds the worker until it unwinds, which reads as a
        # scan in progress unless the client is told to come back.
        patch_scan_jobs(
            mocker,
            running=make_job(
                SCAN_PLATFORMS_FUNC, status=JobStatus.CANCELED, task_name="Quick Scan"
            ),
        )
        mocker.patch.object(scan_module.scan_queue, "enqueue")

        await scan_handler("sid", {"type": "quick"})

        assert "still stopping" in emit.await_args.args[1]

    async def test_refusal_reports_a_queued_scan_as_queued(self, mocker, emit):
        patch_scan_jobs(
            mocker, scan_queued=[make_job(SCAN_PLATFORMS_FUNC, task_name="Full Scan")]
        )
        mocker.patch.object(scan_module.scan_queue, "enqueue")

        await scan_handler("sid", {"type": "quick"})

        assert emit.await_args.args[1] == "Full Scan is already queued"

    async def test_a_rom_scan_is_accepted_while_a_library_scan_runs(self, mocker, emit):
        # The metadata refresh dialog fans a multi-platform selection into one
        # request per platform, so each one has to be accepted.
        patch_scan_jobs(mocker, running=make_job(SCAN_PLATFORMS_FUNC))
        enqueue = mocker.patch.object(scan_module.scan_queue, "enqueue")

        await scan_handler("sid", {"type": "quick", "roms_ids": [7]})

        enqueue.assert_called_once()
        assert enqueue.call_args.kwargs["at_front"] is True

    async def test_a_library_scan_does_not_ask_to_jump_the_queue(self, mocker, emit):
        patch_scan_jobs(mocker)
        enqueue = mocker.patch.object(scan_module.scan_queue, "enqueue")

        await scan_handler("sid", {"type": "quick"})

        assert enqueue.call_args.kwargs["at_front"] is False

    async def test_a_running_rom_scan_does_not_block_a_library_scan(self, mocker, emit):
        # It is done in seconds, so the library scan just queues behind it.
        patch_scan_jobs(mocker, running=make_scoped_job())
        enqueue = mocker.patch.object(scan_module.scan_queue, "enqueue")

        await scan_handler("sid", {"type": "quick"})

        enqueue.assert_called_once()

    async def test_a_queued_rom_scan_does_not_block_a_library_scan(self, mocker, emit):
        patch_scan_jobs(mocker, scan_queued=[make_scoped_job()])
        enqueue = mocker.patch.object(scan_module.scan_queue, "enqueue")

        await scan_handler("sid", {"type": "quick"})

        enqueue.assert_called_once()

    async def test_refuses_when_the_scheduled_rescan_is_running(self, mocker, emit):
        # Every task runs through the same runner, so the scheduled rescan is
        # only recognisable by the type its job carries.
        patch_scan_jobs(mocker, running=make_task_job())
        enqueue = mocker.patch.object(scan_module.scan_queue, "enqueue")

        await scan_handler("sid", {"type": "quick"})

        enqueue.assert_not_called()

    async def test_ignores_unrelated_jobs(self, mocker, emit):
        # Only scans block scans; a cleanup or metadata task must not.
        patch_scan_jobs(
            mocker,
            running=make_job(NON_SCAN_FUNC),
            scan_queued=[make_job(NON_SCAN_FUNC)],
            low_queued=[make_job(NON_SCAN_FUNC)],
            scheduled=[make_job(NON_SCAN_FUNC, status=JobStatus.SCHEDULED)],
        )
        enqueue = mocker.patch.object(scan_module.scan_queue, "enqueue")

        await scan_handler("sid", {"type": "quick"})

        enqueue.assert_called_once()


class TestStopFlagOwnership:
    """A starting scan must not erase a stop request aimed at another scan."""

    @pytest.fixture(autouse=True)
    def bail_out_early(self, mocker):
        """Return from scan_platforms right after the stop flag is handled."""
        mocker.patch.object(
            scan_module, "_get_socket_manager", return_value=AsyncMock()
        )
        mocker.patch.object(
            scan_module, "begin_ss_scan", new=AsyncMock(return_value=None)
        )
        mocker.patch.object(
            scan_module.fs_platform_handler,
            "get_platforms",
            AsyncMock(side_effect=FolderStructureNotMatchException()),
        )

    @pytest.fixture
    def redis(self, mocker):
        return mocker.patch.object(scan_module, "redis_client")

    async def test_clears_a_stale_flag_when_no_scan_is_running(self, mocker, redis):
        patch_scan_jobs(mocker)
        mocker.patch.object(scan_module, "get_current_job", return_value=None)

        await scan_platforms(platform_ids=[], metadata_sources=[])

        redis.delete.assert_called_once_with(scan_module.STOP_SCAN_FLAG)

    async def test_clears_the_flag_set_against_itself(self, mocker, redis):
        own_job = make_job(SCAN_PLATFORMS_FUNC)
        patch_scan_jobs(mocker, running=own_job)
        mocker.patch.object(scan_module, "get_current_job", return_value=own_job)

        await scan_platforms(platform_ids=[], metadata_sources=[])

        redis.delete.assert_called_once_with(scan_module.STOP_SCAN_FLAG)

    async def test_leaves_another_running_scans_flag_alone(self, mocker, redis):
        # The other scan may not have polled the flag yet, and dropping it here
        # would let a scan the user stopped carry on to completion.
        patch_scan_jobs(mocker, running=make_job(SCAN_PLATFORMS_FUNC))
        mocker.patch.object(
            scan_module, "get_current_job", return_value=make_job(SCAN_PLATFORMS_FUNC)
        )

        await scan_platforms(platform_ids=[], metadata_sources=[])

        redis.delete.assert_not_called()


class TestStopScan:
    """Stopping must clear queued scans as well as the running one."""

    @pytest.fixture
    def emit(self, mocker):
        emit = AsyncMock()
        mocker.patch.object(scan_module.socket_handler.socket_server, "emit", emit)
        return emit

    @pytest.fixture(autouse=True)
    def authorized(self, mocker):
        user = MagicMock()
        user.oauth_scopes = [Scope.TASKS_RUN]
        mocker.patch.object(
            scan_module, "get_authenticated_user", AsyncMock(return_value=user)
        )

    @pytest.fixture
    def redis(self, mocker):
        return mocker.patch.object(scan_module, "redis_client")

    async def test_sets_stop_flag_for_running_scan(self, mocker, emit, redis):
        running = make_job(SCAN_PLATFORMS_FUNC)
        patch_scan_jobs(mocker, running=running)

        await stop_scan_handler("sid")

        running.cancel.assert_called_once()
        redis.set.assert_called_once_with(scan_module.STOP_SCAN_FLAG, 1)

    async def test_sets_stop_flag_for_running_scheduled_rescan(
        self, mocker, emit, redis
    ):
        # The flag is the only channel an in-flight scan polls, so missing the
        # scheduled rescan here makes stopping it a silent no-op.
        running = make_task_job()
        patch_scan_jobs(mocker, running=running)

        await stop_scan_handler("sid")

        redis.set.assert_called_once_with(scan_module.STOP_SCAN_FLAG, 1)

    async def test_cancels_queued_scans(self, mocker, emit, redis):
        queued = [make_job(SCAN_PLATFORMS_FUNC), make_job(SCAN_PLATFORMS_FUNC)]
        patch_scan_jobs(
            mocker, running=make_job(SCAN_PLATFORMS_FUNC), scan_queued=queued
        )

        await stop_scan_handler("sid")

        for job in queued:
            job.cancel.assert_called_once()

    async def test_a_second_stop_on_an_unwinding_scan_is_not_an_error(
        self, mocker, emit, redis
    ):
        # The first Stop marks the job cancelled, but the worker still holds it
        # while it unwinds, so the second Stop reaches it again.
        running = make_job(SCAN_PLATFORMS_FUNC, status=JobStatus.CANCELED)
        running.cancel.side_effect = InvalidJobOperation
        patch_scan_jobs(mocker, running=running)

        await stop_scan_handler("sid")

        redis.set.assert_called_once_with(scan_module.STOP_SCAN_FLAG, 1)

    async def test_cancels_watcher_scans(self, mocker, emit, redis):
        # Cancelling only the high priority queue would hand the worker the
        # watcher's scan the moment the running one unwinds.
        low_queued = make_job(SCAN_PLATFORMS_FUNC)
        scheduled = make_job(SCAN_PLATFORMS_FUNC, status=JobStatus.SCHEDULED)
        patch_scan_jobs(mocker, low_queued=[low_queued], scheduled=[scheduled])

        await stop_scan_handler("sid")

        low_queued.cancel.assert_called_once()
        # Cancelling a delayed job takes it out of the scheduled registry too,
        # so nothing releases it once the delay is up.
        scheduled.cancel.assert_called_once()

    async def test_cancels_queued_scans_with_none_running(self, mocker, emit, redis):
        # Stopping a scan that has not been picked up yet must still drop it,
        # and must not leave a stop flag behind for the next scan to trip on.
        queued = [make_job(SCAN_PLATFORMS_FUNC)]
        patch_scan_jobs(mocker, scan_queued=queued)

        await stop_scan_handler("sid")

        queued[0].cancel.assert_called_once()
        redis.set.assert_not_called()

    async def test_no_scan_to_stop(self, mocker, emit, redis):
        patch_scan_jobs(mocker)

        await stop_scan_handler("sid")

        redis.set.assert_not_called()


class TestReportScanFailure:
    """A scan whose worker died cannot report itself, so RQ reports for it."""

    @pytest.fixture
    def emit(self, mocker):
        manager = AsyncMock()
        mocker.patch.object(scan_module, "_get_socket_manager", return_value=manager)
        return manager.emit

    def test_reports_a_scan_its_worker_abandoned(self, emit):
        scan_module.report_scan_failure(
            make_job(SCAN_PLATFORMS_FUNC),
            MagicMock(),
            AbandonedJobError,
            AbandonedJobError(),
            None,
        )

        emit.assert_awaited_once()
        assert emit.await_args.args[0] == "scan:done_ko"

    def test_stays_quiet_for_a_failure_the_scan_already_reported(self, emit):
        # scan_platforms emits on its way out, so reporting here would double up.
        scan_module.report_scan_failure(
            make_job(SCAN_PLATFORMS_FUNC),
            MagicMock(),
            RuntimeError,
            RuntimeError("boom"),
            None,
        )

        emit.assert_not_awaited()

    def test_swallows_a_report_that_cannot_be_sent(self, emit):
        # RQ re-raises out of the registry sweep that calls this, which would
        # leave the abandoned scans in the registry and stop the worker.
        emit.side_effect = ConnectionError("redis is gone")

        scan_module.report_scan_failure(
            make_job(SCAN_PLATFORMS_FUNC),
            MagicMock(),
            AbandonedJobError,
            AbandonedJobError(),
            None,
        )

        emit.assert_called_once()


def test_scan_stats_reports_file_counters():
    stats = ScanStats(updated_roms=2, new_files=5)

    assert stats.to_dict()["updated_roms"] == 2
    assert stats.to_dict()["new_files"] == 5


class TestQuickScanCoversRomFiles:
    def test_quick_scan_covers_new_and_existing_roms(self, rom: Rom):
        assert should_scan_rom(ScanType.QUICK, None, [], []) is True
        assert should_scan_rom(ScanType.QUICK, rom, [], []) is True

    def test_scoped_quick_scan_respects_roms_ids(self, rom: Rom):
        assert should_scan_rom(ScanType.QUICK, None, [rom.id], []) is False
        assert should_scan_rom(ScanType.QUICK, rom, [rom.id + 99], []) is False
        assert should_scan_rom(ScanType.QUICK, rom, [rom.id], []) is True


class TestShouldHashIncrementally:
    def test_selected_metadata_scans_are_incremental(self, rom: Rom):
        assert _should_hash_incrementally(ScanType.UPDATE, rom, [rom.id]) is True
        assert _should_hash_incrementally(ScanType.UNMATCHED, rom, [rom.id]) is True
        assert _should_hash_incrementally(ScanType.UPDATE, rom, []) is False
        assert _should_hash_incrementally(ScanType.UPDATE, rom, [rom.id + 1]) is False

    @pytest.mark.parametrize("scan_type", [ScanType.COMPLETE, ScanType.HASHES])
    def test_full_rescans_read_every_file(self, rom: Rom, scan_type: ScanType):
        assert _should_hash_incrementally(scan_type, rom, [rom.id]) is False


@pytest.fixture
def identify_harness(mocker):
    """`_identify_rom` with every collaborator stubbed, so a scan type's
    control flow can be asserted without a database or a filesystem."""
    mocker.patch.object(scan_module, "redis_client", Mock(get=Mock(return_value=None)))

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
    get_rom_files = mocker.patch.object(
        fs,
        "get_rom_files",
        AsyncMock(
            return_value=ParsedRomFiles(
                rom_files=[], crc_hash="", md5_hash="", sha1_hash="", ra_hash=""
            )
        ),
    )

    config = MagicMock()
    config.SKIP_HASH_CALCULATION = False
    config.SKIP_TITLE_ID_EXTRACTION = False
    config.EMBED_SWITCH_TITLE_IDS = False
    mocker.patch.object(scan_module.cm, "get_config", return_value=config)

    scan_rom = mocker.patch.object(
        scan_module, "scan_rom", AsyncMock(return_value=MagicMock(is_identified=False))
    )

    mocker.patch.object(scan_module, "fs_resource_handler", new=AsyncMock())
    mocker.patch.object(scan_module, "download_rom_resources", new=AsyncMock())
    mocker.patch.object(scan_module, "SimpleRomSchema", MagicMock())

    db = mocker.patch.object(scan_module, "db_rom_handler")
    db.add_rom.return_value = MagicMock(
        is_identified=False, id=1, url_cover="", url_manual="", url_screenshots=[]
    )
    db.get_matching_missing_rom.return_value = None
    db.sync_rom_files.return_value = SyncedRomFiles(files=[], orphaned_cover_paths=[])

    loaded_rom_files = mocker.patch.object(
        scan_module, "loaded_rom_files", return_value=["stored-row"]
    )
    refresh = mocker.patch.object(
        scan_module,
        "refresh_rom_files",
        AsyncMock(
            return_value=RomFilesRefresh(new_files=2, updated_files=0, removed_files=1)
        ),
    )

    def existing_rom() -> Rom:
        rom = Rom(platform_id=1, fs_name="Game", fs_path="test/roms")
        rom.id = 1
        return rom

    async def run(
        rom: Rom | None,
        scan_type: ScanType,
        roms_ids: list[int],
        socket_manager: AsyncMock | None = None,
        scan_stats: AsyncMock | None = None,
    ) -> None:
        fs_rom: FSRom = {
            "fs_name": "Game",
            "flat": False,
            "nested": True,
            "files": [],
            "crc_hash": "",
            "md5_hash": "",
            "sha1_hash": "",
            "ra_hash": "",
        }
        platform = Platform(name="Test", slug="test", fs_slug="test")
        platform.id = 1
        await _identify_rom(
            platform=platform,
            fs_rom=fs_rom,
            rom=rom,
            scan_type=scan_type,
            roms_ids=roms_ids,
            metadata_sources=[],
            launchbox_remote_enabled=False,
            playmatch_enabled=False,
            socket_manager=socket_manager or AsyncMock(),
            scan_stats=scan_stats or AsyncMock(),
            scanned_rom_ids=set(),
        )

    return SimpleNamespace(
        db=db,
        scan_rom=scan_rom,
        get_rom_files=get_rom_files,
        loaded_rom_files=loaded_rom_files,
        refresh=refresh,
        existing_rom=existing_rom,
        run=run,
    )


class TestIdentifyRomFiles:
    """A quick scan hands an existing rom to `refresh_rom_files` and skips the
    metadata pipeline; a rom not yet in the database goes the regular way."""

    async def test_existing_rom_only_refreshes_its_files(self, identify_harness):
        rom = identify_harness.existing_rom()
        socket_manager = AsyncMock()
        scan_stats = AsyncMock()

        await identify_harness.run(
            rom,
            ScanType.QUICK,
            [],
            socket_manager=socket_manager,
            scan_stats=scan_stats,
        )

        identify_harness.refresh.assert_awaited_once_with(rom)
        identify_harness.scan_rom.assert_not_called()
        identify_harness.db.add_rom.assert_not_called()
        scan_stats.increment.assert_awaited_once_with(
            socket_manager=socket_manager, scanned_roms=1, updated_roms=1, new_files=2
        )
        identify_harness.db.get_rom_simple.assert_called_once_with(rom.id)
        socket_manager.emit.assert_awaited_once()
        assert socket_manager.emit.await_args.args[0] == "scan:scanning_rom"

    async def test_unchanged_rom_emits_nothing(self, identify_harness):
        identify_harness.refresh.return_value = RomFilesRefresh(
            new_files=0, updated_files=0, removed_files=0
        )
        socket_manager = AsyncMock()
        scan_stats = AsyncMock()

        await identify_harness.run(
            identify_harness.existing_rom(),
            ScanType.QUICK,
            [],
            socket_manager=socket_manager,
            scan_stats=scan_stats,
        )

        scan_stats.increment.assert_awaited_once_with(
            socket_manager=socket_manager, scanned_roms=1, updated_roms=0, new_files=0
        )
        identify_harness.db.get_rom_simple.assert_not_called()
        socket_manager.emit.assert_not_awaited()

    async def test_new_rom_takes_the_regular_path(self, identify_harness):
        await identify_harness.run(None, ScanType.QUICK, [])

        identify_harness.refresh.assert_not_called()
        identify_harness.scan_rom.assert_awaited_once()
        identify_harness.db.add_rom.assert_called()


class TestIdentifyRomIncrementalHashing:
    """Selected-rom metadata scans hand the stored rows to the file rebuild so
    unchanged files keep their hashes; full rescans read every file."""

    async def test_selected_update_scan_passes_existing_files(self, identify_harness):
        rom = identify_harness.existing_rom()

        await identify_harness.run(rom, ScanType.UPDATE, [rom.id])

        identify_harness.loaded_rom_files.assert_called_once_with(rom)
        kwargs = identify_harness.get_rom_files.await_args.kwargs
        assert kwargs["existing_files"] == ["stored-row"]

    @pytest.mark.parametrize("scan_type", [ScanType.HASHES, ScanType.COMPLETE])
    async def test_full_rescans_rehash_everything(self, identify_harness, scan_type):
        rom = identify_harness.existing_rom()

        await identify_harness.run(rom, scan_type, [rom.id])

        kwargs = identify_harness.get_rom_files.await_args.kwargs
        assert kwargs["existing_files"] is None


class TestIdentifyPlatformLoadsFilesForQuickScan:
    """A quick scan reconciles every existing rom's files, so their rows are
    loaded with the batch lookup instead of one query per rom."""

    @pytest.fixture
    def patched(self, mocker):
        mocker.patch.object(
            scan_module, "redis_client", Mock(get=Mock(return_value=None))
        )

        platform = Platform(name="Test", slug="test", fs_slug="test")
        platform.id = 1
        platform.missing_from_fs = False
        db_platform = mocker.patch.object(scan_module, "db_platform_handler")
        db_platform.get_platform_by_fs_slug.return_value = platform
        db_platform.add_platform.return_value = platform

        mocker.patch.object(
            scan_module, "scan_platform", AsyncMock(return_value=platform)
        )
        mocker.patch.object(
            scan_module.PlatformSchema,
            "model_validate",
            return_value=Mock(model_dump=Mock(return_value={})),
        )
        mocker.patch.object(
            scan_module.fs_firmware_handler,
            "get_firmware",
            AsyncMock(return_value=[]),
        )
        fs_rom: FSRom = {
            "fs_name": "Game",
            "flat": False,
            "nested": True,
            "files": [],
            "crc_hash": "",
            "md5_hash": "",
            "sha1_hash": "",
            "ra_hash": "",
        }
        mocker.patch.object(
            scan_module.fs_rom_handler, "get_roms", AsyncMock(return_value=[fs_rom])
        )
        mocker.patch.object(scan_module, "_identify_rom", AsyncMock())

        rom = Rom(fs_name="Game", platform_id=platform.id)
        rom.id = 42
        db_rom = mocker.patch.object(scan_module, "db_rom_handler")
        db_rom.get_roms_by_fs_name.return_value = {"Game": rom}
        db_rom.get_missing_rom_ids.return_value = set()
        db_rom.mark_missing_roms.return_value = []
        db_firmware = mocker.patch.object(scan_module, "db_firmware_handler")
        db_firmware.mark_missing_firmware.return_value = []
        return db_rom

    @pytest.mark.parametrize(
        "scan_type,with_files", [(ScanType.QUICK, True), (ScanType.COMPLETE, False)]
    )
    async def test_rows_are_loaded_only_for_quick_scans(
        self, patched, scan_type, with_files
    ):
        await scan_module._identify_platform(
            platform_slug="test",
            scan_type=scan_type,
            fs_platforms=["test"],
            roms_ids=[],
            metadata_sources=[],
            launchbox_remote_enabled=False,
            playmatch_enabled=False,
            socket_manager=AsyncMock(),
            scan_stats=AsyncMock(),
            scanned_rom_ids=set(),
        )

        assert patched.get_roms_by_fs_name.call_args.kwargs["with_files"] is with_files
