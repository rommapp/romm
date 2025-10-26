from unittest.mock import AsyncMock, MagicMock

import pytest

from handler.metadata.hasheous_handler import HasheousHandler
from handler.metadata.igdb_handler import IGDBHandler
from handler.metadata.launchbox_handler import LaunchboxHandler
from handler.metadata.moby_handler import MobyGamesHandler
from handler.metadata.ra_handler import RAHandler
from handler.metadata.sgdb_handler import SGDBBaseHandler
from handler.metadata.ss_handler import SSHandler
from handler.scan_handler import MetadataSource, ScanType
from tasks.scheduled.scan_library import ScanLibraryTask, scan_library_task


class TestScanLibraryTask:
    @pytest.fixture
    def task(self):
        return ScanLibraryTask()

    def test_init(self, task):
        """Test task initialization"""
        assert task.func == "tasks.scheduled.scan_library.scan_library_task.run"
        assert task.description == "Rescans the entire library"

    async def test_run_enabled(self, task, mocker):
        """Test run when scheduled rescan is enabled"""
        mocker.patch.object(HasheousHandler, "is_enabled", return_value=False)
        mocker.patch.object(IGDBHandler, "is_enabled", return_value=False)
        mocker.patch.object(LaunchboxHandler, "is_enabled", return_value=True)
        mocker.patch.object(MobyGamesHandler, "is_enabled", return_value=False)
        mocker.patch.object(RAHandler, "is_enabled", return_value=True)
        mocker.patch.object(SGDBBaseHandler, "is_enabled", return_value=False)
        mocker.patch.object(SSHandler, "is_enabled", return_value=False)
        mocker.patch("tasks.scheduled.scan_library.ENABLE_SCHEDULED_RESCAN", True)
        mock_scan_platforms = mocker.patch(
            "tasks.scheduled.scan_library.scan_platforms"
        )
        mock_log = mocker.patch("tasks.scheduled.scan_library.log")
        mock_scan_platforms.return_value = AsyncMock()

        await task.run()

        mock_log.info.assert_any_call("Scheduled library scan started...")
        mock_scan_platforms.assert_called_once_with(
            platform_ids=[],
            metadata_sources=[MetadataSource.RA, MetadataSource.LAUNCHBOX],
            scan_type=ScanType.UPDATE,
        )
        mock_log.info.assert_any_call("Scheduled library scan done")

    async def test_run_disabled(self, task, mocker):
        """Test run when scheduled rescan is disabled"""
        mocker.patch("tasks.scheduled.scan_library.ENABLE_SCHEDULED_RESCAN", False)
        mock_scan_platforms = mocker.patch(
            "tasks.scheduled.scan_library.scan_platforms"
        )
        mock_log = mocker.patch("tasks.scheduled.scan_library.log")
        task.unschedule = MagicMock()

        await task.run()

        mock_log.info.assert_called_once_with(
            "Scheduled library scan not enabled, unscheduling..."
        )
        task.unschedule.assert_called_once()
        mock_scan_platforms.assert_not_called()

    def test_task_instance(self):
        """Test that the module-level task instance is created correctly"""
        assert isinstance(scan_library_task, ScanLibraryTask)
        assert (
            scan_library_task.func
            == "tasks.scheduled.scan_library.scan_library_task.run"
        )
