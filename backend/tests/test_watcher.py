from itertools import count
from unittest.mock import MagicMock, PropertyMock

import pytest
import watcher as watcher_module
from rq.exceptions import DeserializationError
from rq.job import Job
from watcher import EventType, get_pending_scan_coverage, process_changes

from config import LIBRARY_BASE_PATH
from handler.scan_handler import ScanType

_job_ids = count()


def make_job(**kwargs) -> MagicMock:
    """An RQ job stub enqueued the way the scan callers enqueue: keywords only."""
    job = MagicMock(spec=Job)
    job.id = f"job-{next(_job_ids)}"
    job.args = ()
    job.kwargs = kwargs
    return job


def watcher_full_rescan_job() -> MagicMock:
    return make_job(platform_ids=[], scan_type=ScanType.UPDATE)


def watcher_platform_job(platform_id: int) -> MagicMock:
    return make_job(platform_ids=[platform_id], scan_type=ScanType.QUICK)


def scheduled_rescan_job() -> MagicMock:
    """The scheduled rescan goes through the task runner, named by keyword."""
    return make_job(name="scan_library")


def patch_pending_jobs(mocker, *jobs):
    return mocker.patch.object(
        watcher_module, "get_pending_scan_jobs", return_value=list(jobs)
    )


class TestPendingScanCoverage:
    """Scans are enqueued with keywords, so the scope lives in job.kwargs."""

    def test_nothing_pending(self, mocker):
        patch_pending_jobs(mocker)

        coverage = get_pending_scan_coverage()

        assert coverage.full_library == 0
        assert coverage.platform_ids == frozenset()
        assert coverage.platform_fs_slugs == frozenset()

    def test_a_scan_with_no_platform_ids_covers_the_library(self, mocker):
        patch_pending_jobs(mocker, watcher_full_rescan_job())

        assert get_pending_scan_coverage().full_library == 1

    def test_the_scheduled_rescan_task_covers_the_library(self, mocker):
        patch_pending_jobs(mocker, scheduled_rescan_job())

        assert get_pending_scan_coverage().full_library == 1

    def test_full_rescans_are_counted(self, mocker):
        patch_pending_jobs(mocker, watcher_full_rescan_job(), scheduled_rescan_job())

        assert get_pending_scan_coverage().full_library == 2

    def test_scoped_scans_report_their_platforms(self, mocker):
        patch_pending_jobs(
            mocker, watcher_platform_job(1), make_job(platform_ids=[2, 3])
        )

        coverage = get_pending_scan_coverage()

        assert coverage.full_library == 0
        assert coverage.platform_ids == frozenset({1, 2, 3})

    def test_a_socket_scan_scoped_by_slug_reports_its_slugs(self, mocker):
        # The socket accepts folders with no database row, which arrive as slugs.
        patch_pending_jobs(mocker, make_job(platform_ids=[], platform_fs_slugs=["gba"]))

        coverage = get_pending_scan_coverage()

        assert coverage.full_library == 0
        assert coverage.platform_fs_slugs == frozenset({"gba"})

    def test_a_rom_scoped_scan_is_not_a_full_rescan(self, mocker):
        # A scan of selected roms resolves its platforms from the database, so
        # it covers neither the library nor any platform this can name.
        patch_pending_jobs(mocker, make_job(platform_ids=[], roms_ids=[7]))

        coverage = get_pending_scan_coverage()

        assert coverage.full_library == 0
        assert coverage.platform_ids == frozenset()

    def test_a_rom_scoped_scan_does_not_cover_the_platform_it_names(self, mocker):
        # The refresh dialog names the platform alongside the roms, but the scan
        # only touches those roms, so the platform still needs its rescan.
        patch_pending_jobs(mocker, make_job(platform_ids=[1], roms_ids=[7]))

        assert get_pending_scan_coverage().platform_ids == frozenset()

    def test_ignores_positional_arguments(self, mocker):
        # job.args is what the old dedupe read, and it is always empty.
        job = make_job(platform_ids=[1])
        job.args = ([2],)
        patch_pending_jobs(mocker, job)

        assert get_pending_scan_coverage().platform_ids == frozenset({1})

    def test_an_unreadable_payload_is_ignored(self, mocker):
        # Its scope is unknowable, and a duplicate scan costs less than a rescan
        # that never happens because of a job nobody can read.
        job = make_job()
        type(job).kwargs = PropertyMock(side_effect=DeserializationError)
        patch_pending_jobs(mocker, job)

        coverage = get_pending_scan_coverage()

        assert coverage.full_library == 0
        assert coverage.platform_ids == frozenset()


class TestProcessChanges:
    """A filesystem change must not schedule a scan that is already pending."""

    @pytest.fixture(autouse=True)
    def library_layout(self, mocker):
        config = MagicMock()
        config.has_structure_path_b = False
        config.EXCLUDED_SINGLE_FILES = []
        config.EXCLUDED_MULTI_FILES = []
        config.EXCLUDED_MULTI_PARTS_FILES = []
        mocker.patch.object(watcher_module.cm, "get_config", return_value=config)
        mocker.patch.object(
            watcher_module.meta_igdb_handler, "is_enabled", return_value=True
        )

    @pytest.fixture
    def platform(self, mocker):
        db_platform = MagicMock(id=1, fs_slug="gba")
        mocker.patch.object(
            watcher_module.db_platform_handler,
            "get_platform_by_fs_slug",
            return_value=db_platform,
        )
        return db_platform

    @pytest.fixture
    def enqueue_in(self, mocker):
        return mocker.patch.object(watcher_module.scan_queue, "enqueue_in")

    def rom_change(self, fs_slug: str = "gba"):
        return (EventType.ADDED, f"{LIBRARY_BASE_PATH}/roms/{fs_slug}/game.gba")

    def platform_dir_change(self, fs_slug: str = "gba"):
        return (EventType.ADDED, f"{LIBRARY_BASE_PATH}/roms/{fs_slug}")

    def test_schedules_a_quick_scan_for_the_changed_platform(
        self, mocker, platform, enqueue_in
    ):
        patch_pending_jobs(mocker)

        process_changes([self.rom_change()])

        enqueue_in.assert_called_once()
        kwargs = enqueue_in.call_args.kwargs
        assert kwargs["platform_ids"] == [platform.id]
        assert kwargs["scan_type"] == ScanType.QUICK
        assert kwargs["meta"]["task_name"] == "Quick Scan"

    def test_a_platform_directory_change_schedules_a_full_rescan(
        self, mocker, platform, enqueue_in
    ):
        patch_pending_jobs(mocker)

        process_changes([self.platform_dir_change()])

        enqueue_in.assert_called_once()
        kwargs = enqueue_in.call_args.kwargs
        assert kwargs["platform_ids"] == []
        assert kwargs["scan_type"] == ScanType.UPDATE

    def test_a_pending_full_rescan_absorbs_every_change(
        self, mocker, platform, enqueue_in
    ):
        patch_pending_jobs(mocker, watcher_full_rescan_job())

        process_changes([self.rom_change()])

        enqueue_in.assert_not_called()

    def test_a_pending_scheduled_rescan_absorbs_every_change(
        self, mocker, platform, enqueue_in
    ):
        patch_pending_jobs(mocker, scheduled_rescan_job())

        process_changes([self.rom_change()])

        enqueue_in.assert_not_called()

    def test_a_pending_scan_for_the_platform_is_not_duplicated(
        self, mocker, platform, enqueue_in
    ):
        patch_pending_jobs(mocker, watcher_platform_job(platform.id))

        process_changes([self.rom_change()])

        enqueue_in.assert_not_called()

    def test_a_pending_scan_scoped_by_slug_is_not_duplicated(
        self, mocker, platform, enqueue_in
    ):
        patch_pending_jobs(mocker, make_job(platform_fs_slugs=[platform.fs_slug]))

        process_changes([self.rom_change()])

        enqueue_in.assert_not_called()

    def test_a_pending_scan_for_another_platform_does_not_block(
        self, mocker, platform, enqueue_in
    ):
        patch_pending_jobs(mocker, watcher_platform_job(platform.id + 1))

        process_changes([self.rom_change()])

        enqueue_in.assert_called_once()

    def test_a_platform_missing_from_the_database_is_skipped(self, mocker, enqueue_in):
        patch_pending_jobs(mocker)
        mocker.patch.object(
            watcher_module.db_platform_handler,
            "get_platform_by_fs_slug",
            return_value=None,
        )

        process_changes([self.rom_change()])

        enqueue_in.assert_not_called()

    def test_a_pending_scan_scoped_to_another_slug_does_not_block(
        self, mocker, platform, enqueue_in
    ):
        # A slug-scoped scan names no platform id, which must not be mistaken
        # for a scan of the whole library.
        patch_pending_jobs(mocker, make_job(platform_fs_slugs=["snes"]))

        process_changes([self.rom_change()])

        enqueue_in.assert_called_once()

    def test_a_pending_rom_scoped_scan_does_not_block(
        self, mocker, platform, enqueue_in
    ):
        patch_pending_jobs(mocker, make_job(roms_ids=[7]))

        process_changes([self.rom_change()])

        enqueue_in.assert_called_once()
