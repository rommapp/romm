import os
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

    def test_disabled_by_default(self, task):
        # The run-task endpoint rejects a task unless both flags are set, so a
        # disabled schedule also means no manual runs.
        assert task.enabled is False
        assert task.manual_run is True
        assert task.can_run_manually is False

    def test_enabled_follows_config_flag(self):
        with patch.object(mod, "ENABLE_SCHEDULED_CLEANUP_ORPHANED_RESOURCES", True):
            task = CleanupOrphanedResourcesTask()
            assert task.enabled is True
            assert task.can_run_manually is True

    def test_cron_string_uses_configured_schedule(self, task):
        assert task.cron_string == mod.SCHEDULED_CLEANUP_ORPHANED_RESOURCES_CRON

    def test_cron_string_follows_config_override(self):
        with patch.object(
            mod, "SCHEDULED_CLEANUP_ORPHANED_RESOURCES_CRON", "30 2 * * *"
        ):
            assert CleanupOrphanedResourcesTask().cron_string == "30 2 * * *"

    def test_init_unschedules_when_no_cron(self, task):
        task.cron_string = None

        with patch.object(task, "unschedule") as mock_unschedule:
            assert task.init() is None
            mock_unschedule.assert_called_once()

    def test_init_schedules_when_enabled(self, task):
        task.enabled = True
        task.cron_string = "0 5 * * *"

        with patch.object(task, "_get_existing_job", return_value=None):
            with patch.object(task, "schedule") as mock_schedule:
                task.init()
                mock_schedule.assert_called_once()

    def test_init_does_not_schedule_when_disabled(self, task):
        with patch.object(task, "_get_existing_job", return_value=None):
            with patch.object(task, "schedule") as mock_schedule:
                assert task.init() is None
                mock_schedule.assert_not_called()


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


class TestScanResourceDirs:
    """The resource tree walk backing the cleanup task."""

    @staticmethod
    def _make_tree(root, layout: dict[int, list[int]]) -> None:
        for platform_id, rom_ids in layout.items():
            for rom_id in rom_ids:
                (root / str(platform_id) / str(rom_id)).mkdir(parents=True)

    def test_maps_platforms_to_rom_dirs(self, tmp_path):
        self._make_tree(tmp_path, {1: [10, 11], 2: [20]})

        assert mod._scan_resource_dirs(str(tmp_path)) == {1: {10, 11}, 2: {20}}

    def test_ignores_non_numeric_names(self, tmp_path):
        self._make_tree(tmp_path, {1: [10]})
        (tmp_path / "not-a-platform").mkdir()
        (tmp_path / "1" / "not-a-rom").mkdir()

        assert mod._scan_resource_dirs(str(tmp_path)) == {1: {10}}

    def test_ignores_files(self, tmp_path):
        self._make_tree(tmp_path, {1: [10]})
        (tmp_path / "2").write_text("stray file named like a platform")
        (tmp_path / "1" / "20").write_text("stray file named like a rom")

        assert mod._scan_resource_dirs(str(tmp_path)) == {1: {10}}

    def test_empty_tree(self, tmp_path):
        assert mod._scan_resource_dirs(str(tmp_path)) == {}

    def test_platform_with_no_rom_dirs(self, tmp_path):
        (tmp_path / "1").mkdir()

        assert mod._scan_resource_dirs(str(tmp_path)) == {1: set()}

    def test_unreadable_directory_yields_empty_set(self, tmp_path):
        # A directory that disappears or denies access must not abort the walk,
        # otherwise one bad platform would strand every other platform's orphans.
        self._make_tree(tmp_path, {1: [10]})

        real_scandir = os.scandir

        def flaky_scandir(path):
            if path.endswith(os.sep + "1"):
                raise PermissionError(13, "Permission denied")
            return real_scandir(path)

        with patch.object(mod.os, "scandir", side_effect=flaky_scandir):
            assert mod._scan_resource_dirs(str(tmp_path)) == {1: set()}
