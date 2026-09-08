from unittest.mock import AsyncMock, MagicMock

import pytest

from config import SCAN_TIMEOUT
from handler.scan_handler import MetadataSource, ScanType
from tasks.scheduled import scan_library
from tasks.scheduled.scan_library import ScanLibraryTask, scan_library_task


class TestScanLibraryTask:
    @pytest.fixture
    def task(self):
        return ScanLibraryTask()

    @pytest.fixture
    def providers(self, mocker):
        """Every metadata provider off, read from the task itself so one
        configured in the environment cannot add itself to the scan."""
        handlers = {
            name: handler
            for name, handler in vars(scan_library).items()
            if name.startswith("meta_") and hasattr(handler, "is_enabled")
        }
        for handler in handlers.values():
            mocker.patch.object(handler, "is_enabled", return_value=False)
        return handlers

    def test_init(self, task):
        """Test task initialization"""
        assert task.description == "Rescans the entire library"

    async def test_run_enabled(self, task, mocker, providers):
        """Test run when scheduled rescan is enabled"""
        for name in ("meta_ra_handler", "meta_launchbox_handler"):
            mocker.patch.object(providers[name], "is_enabled", return_value=True)
        mocker.patch("tasks.scheduled.scan_library.ENABLE_SCHEDULED_RESCAN", True)

        scan_result = MagicMock()
        mock_scan_platforms = mocker.patch(
            "tasks.scheduled.scan_library.scan_platforms",
            side_effect=AsyncMock(return_value=scan_result),
        )
        mock_log = mocker.patch("tasks.scheduled.scan_library.log")

        await task.run()

        mock_log.info.assert_any_call("Scheduled library scan started...")
        mock_scan_platforms.assert_called_once_with(
            platform_ids=[],
            metadata_sources=[MetadataSource.RA, MetadataSource.LAUNCHBOX],
            scan_type=ScanType.QUICK,
        )
        mock_log.info.assert_any_call("Scheduled library scan done")

    async def test_run_disabled(self, task, mocker):
        """Test run when scheduled rescan is disabled"""
        mocker.patch("tasks.scheduled.scan_library.ENABLE_SCHEDULED_RESCAN", False)
        mock_scan_platforms = mocker.patch(
            "tasks.scheduled.scan_library.scan_platforms"
        )
        mock_log = mocker.patch("tasks.scheduled.scan_library.log")

        await task.run()

        mock_log.info.assert_called_once_with(
            "Scheduled library scan not enabled, skipping..."
        )
        mock_scan_platforms.assert_not_called()

    def test_task_instance(self):
        """Test that the module-level task instance is created correctly"""
        assert isinstance(scan_library_task, ScanLibraryTask)


def test_scheduled_rescan_gets_the_scan_timeout():
    """It inherits the five-minute task timeout otherwise, which kills it."""
    assert scan_library_task.timeout == SCAN_TIMEOUT
