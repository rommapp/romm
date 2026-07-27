from types import SimpleNamespace
from unittest.mock import patch

import pytest

import tasks.scheduled.cleanup_orphaned_resources as mod
from tasks.scheduled.cleanup_orphaned_resources import CleanupOrphanedResourcesTask


class TestCleanupOrphanedResourcesTask:
    @pytest.fixture
    def task(self):
        return CleanupOrphanedResourcesTask()

    def test_func_points_at_scheduled_module(self, task):
        assert (
            task.func
            == "tasks.scheduled.cleanup_orphaned_resources.cleanup_orphaned_resources_task.run"
        )

    def test_stays_manually_runnable(self, task):
        # The run-task endpoint rejects a task unless both flags are set, so
        # these must hold regardless of whether the cron schedule is on.
        assert task.enabled is True
        assert task.manual_run is True

    def test_no_cron_string_by_default(self, task):
        assert task.cron_string is None

    def test_cron_string_set_when_schedule_enabled(self):
        with patch.object(mod, "ENABLE_SCHEDULED_CLEANUP_ORPHANED_RESOURCES", True):
            with patch.object(
                mod, "SCHEDULED_CLEANUP_ORPHANED_RESOURCES_CRON", "0 5 * * *"
            ):
                assert CleanupOrphanedResourcesTask().cron_string == "0 5 * * *"

    def test_init_unschedules_when_no_cron(self, task):
        with patch.object(task, "unschedule") as mock_unschedule:
            assert task.init() is None
            mock_unschedule.assert_called_once()

    def test_init_schedules_when_cron_set(self, task):
        task.cron_string = "0 5 * * *"

        with patch.object(task, "_get_existing_job", return_value=None):
            with patch.object(task, "schedule") as mock_schedule:
                task.init()
                mock_schedule.assert_called_once()


class TestCleanupOrphanedResourcesRun:
    @pytest.fixture
    def resources_path(self, tmp_path, mocker):
        mocker.patch.object(mod, "RESOURCES_BASE_PATH", str(tmp_path))
        (tmp_path / "roms").mkdir()
        return tmp_path

    @staticmethod
    def _make_dirs(resources_path, platform_id: int, rom_ids: list[int]) -> None:
        for rom_id in rom_ids:
            (resources_path / "roms" / str(platform_id) / str(rom_id)).mkdir(
                parents=True
            )

    @staticmethod
    def _mock_db(mocker, library: dict[int, list[int]]) -> None:
        """Make the database report `library`, a mapping of platform id to ROM ids."""
        mocker.patch.object(
            mod.db_platform_handler,
            "get_platforms",
            return_value=[SimpleNamespace(id=pid) for pid in library],
        )
        mocker.patch.object(
            mod.db_rom_handler,
            "get_roms_scalar",
            side_effect=lambda platform_ids: [
                SimpleNamespace(id=rom_id) for rom_id in library[platform_ids[0]]
            ],
        )

    async def test_skips_when_db_empty_and_filesystem_populated(
        self, resources_path, mocker
    ):
        self._make_dirs(resources_path, 1, [10])
        self._make_dirs(resources_path, 2, [20])
        self._mock_db(mocker, {})

        stats = await CleanupOrphanedResourcesTask().run()

        assert stats["platforms_in_fs"] == 2
        assert stats["removed_fs_platforms"] == 0
        assert stats["removed_fs_roms"] == 0
        assert (resources_path / "roms" / "1" / "10").exists()
        assert (resources_path / "roms" / "2" / "20").exists()

    async def test_force_cleans_up_when_db_empty(self, resources_path, mocker):
        self._make_dirs(resources_path, 1, [10])
        self._mock_db(mocker, {})

        stats = await CleanupOrphanedResourcesTask().run(force=True)

        assert stats["removed_fs_platforms"] == 1
        assert not (resources_path / "roms" / "1").exists()

    async def test_removes_orphans_when_db_reports_platforms(
        self, resources_path, mocker
    ):
        self._make_dirs(resources_path, 1, [10, 11])
        self._make_dirs(resources_path, 2, [20])
        self._mock_db(mocker, {1: [10]})

        stats = await CleanupOrphanedResourcesTask().run()

        assert stats["removed_fs_platforms"] == 1
        assert stats["removed_fs_roms"] == 2
        assert (resources_path / "roms" / "1" / "10").exists()
        assert not (resources_path / "roms" / "1" / "11").exists()
        assert not (resources_path / "roms" / "2").exists()

    async def test_empty_db_and_empty_filesystem_is_not_skipped(
        self, resources_path, mocker
    ):
        self._mock_db(mocker, {})

        stats = await CleanupOrphanedResourcesTask().run()

        assert stats["platforms_in_fs"] == 0
        assert stats["removed_fs_platforms"] == 0
