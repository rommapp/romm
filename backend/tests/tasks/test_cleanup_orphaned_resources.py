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
