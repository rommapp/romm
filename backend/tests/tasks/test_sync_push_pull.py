"""Tests for SyncPushPullTask initialization and configuration."""

from unittest.mock import patch

import pytest

from tasks.sync_push_pull_task import SyncPushPullTask, sync_push_pull_task
from tasks.tasks import PeriodicTask, TaskType


class TestSyncPushPullTaskInit:
    @pytest.fixture
    def task(self):
        return SyncPushPullTask()

    def test_init(self, task: SyncPushPullTask):
        assert task.title == "Push-Pull Sync"
        assert task.description == "Sync saves with devices via SSH/SFTP"
        assert task.task_type == TaskType.SYNC
        assert task.func == "tasks.sync_push_pull_task.run_push_pull_sync"

    def test_is_periodic_task(self, task: SyncPushPullTask):
        assert isinstance(task, PeriodicTask)

    def test_module_singleton_exists(self):
        assert sync_push_pull_task is not None
        assert isinstance(sync_push_pull_task, SyncPushPullTask)

    def test_cron_string_set(self, task: SyncPushPullTask):
        assert task.cron_string is not None


class TestRunPushPullSync:
    @patch("tasks.sync_push_pull_task.ENABLE_SYNC_PUSH_PULL", False)
    async def test_run_disabled_returns_disabled(self):
        from tasks.sync_push_pull_task import run_push_pull_sync

        result = await run_push_pull_sync()
        assert result["status"] == "disabled"

    @patch("tasks.sync_push_pull_task.ENABLE_SYNC_PUSH_PULL", True)
    @patch("tasks.sync_push_pull_task.db_device_handler")
    async def test_run_no_devices(self, mock_device_handler):
        from tasks.sync_push_pull_task import run_push_pull_sync

        mock_device_handler.get_all_devices_by_sync_mode.return_value = []

        result = await run_push_pull_sync()
        assert result["status"] == "no_devices"

    @patch("tasks.sync_push_pull_task.ENABLE_SYNC_PUSH_PULL", True)
    @patch("tasks.sync_push_pull_task.db_device_handler")
    async def test_run_device_not_found(self, mock_device_handler):
        from tasks.sync_push_pull_task import run_push_pull_sync

        mock_device_handler.get_device_by_id.return_value = None

        result = await run_push_pull_sync(device_id="nonexistent")
        assert result["status"] == "error"
        assert "not found" in result["message"]

    @patch("tasks.sync_push_pull_task.ENABLE_SYNC_PUSH_PULL", False)
    async def test_run_force_override(self):
        from tasks.sync_push_pull_task import run_push_pull_sync

        with patch("tasks.sync_push_pull_task.db_device_handler") as mock_handler:
            mock_handler.get_device_by_id.return_value = None
            result = await run_push_pull_sync(device_id="test", force=True)
            assert result["status"] == "error"  # Device not found, but didn't skip
