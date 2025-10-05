import os
from unittest.mock import AsyncMock, patch

import anyio
import pytest

from handler.metadata.launchbox_handler import (
    LAUNCHBOX_FILES_KEY,
    LAUNCHBOX_MAME_KEY,
    LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY,
    LAUNCHBOX_METADATA_DATABASE_ID_KEY,
    LAUNCHBOX_METADATA_IMAGE_KEY,
    LAUNCHBOX_METADATA_NAME_KEY,
    LAUNCHBOX_PLATFORMS_KEY,
    LaunchboxHandler,
)
from tasks.scheduled.update_launchbox_metadata import (
    UpdateLaunchboxMetadataTask,
    update_launchbox_metadata_task,
)
from tasks.tasks import RemoteFilePullTask


@pytest.fixture
def task() -> UpdateLaunchboxMetadataTask:
    """Create a task instance for testing"""
    return UpdateLaunchboxMetadataTask()


@pytest.fixture
def sample_zip_content() -> bytes:
    test_dir = os.path.dirname(__file__)
    sample_path = os.path.join(test_dir, "fixtures", "sample_metadata.zip")

    with open(sample_path, "rb") as f:
        return f.read()


@pytest.fixture
def corrupt_zip_content() -> bytes:
    """Create corrupt ZIP content for testing error handling"""
    return b"not a valid zip file"


class TestUpdateLaunchboxMetadataTask:
    """Test suite for UpdateLaunchboxMetadataTask"""

    def test_task_initialization(self, task):
        """Test task initialization with correct parameters"""
        assert (
            task.func
            == "tasks.scheduled.update_launchbox_metadata.update_launchbox_metadata_task.run"
        )
        assert task.description == "Updates the LaunchBox metadata store"
        assert task.url == "https://gamesdb.launchbox-app.com/Metadata.zip"

    @patch.object(RemoteFilePullTask, "run")
    async def test_run_when_launchbox_api_enabled(
        self, mock_super_run, task, sample_zip_content
    ):
        """Test run method when Launchbox API is enabled"""
        mock_super_run.return_value = sample_zip_content

        await task.run(force=True)

        mock_super_run.assert_called_once_with(True)

    async def test_run_when_launchbox_api_disabled(self, task, mocker):
        """Test run method when Launchbox API is disabled"""
        mocker.patch.object(LaunchboxHandler, "is_enabled", return_value=False)
        mock_log = mocker.patch("tasks.scheduled.update_launchbox_metadata.log")

        await task.run(force=True)

        mock_log.warning.assert_called_once_with(
            "Launchbox API is not enabled, skipping metadata update"
        )

    @patch.object(RemoteFilePullTask, "run")
    @patch("tasks.scheduled.update_launchbox_metadata.log")
    async def test_run_when_content_is_none(self, mock_log, mock_super_run, task):
        """Test run method when super().run() returns None"""
        mock_super_run.return_value = None

        await task.run(force=True)

        mock_super_run.assert_called_once()

        mock_log.warning.assert_called_once_with(
            "No content received from launchbox metadata update"
        )

    @patch.object(RemoteFilePullTask, "run")
    @patch("tasks.scheduled.update_launchbox_metadata.log")
    async def test_run_with_corrupt_zip_file(
        self, mock_log, mock_super_run, task, corrupt_zip_content
    ):
        """Test run method with corrupt ZIP file"""
        mock_super_run.return_value = corrupt_zip_content

        await task.run(force=True)

        mock_log.error.assert_called_once_with(
            "Bad zip file in launchbox metadata update"
        )

    @patch.object(RemoteFilePullTask, "run")
    @patch("tasks.scheduled.update_launchbox_metadata.log")
    async def test_run_successful_completion(
        self, mock_log, mock_super_run, task, sample_zip_content
    ):
        """Test successful completion of the task"""
        mock_super_run.return_value = sample_zip_content

        await task.run(force=True)

        mock_log.info.assert_called_with(
            "Scheduled launchbox metadata update completed!"
        )

    @patch.object(RemoteFilePullTask, "run")
    @patch("tasks.scheduled.update_launchbox_metadata.async_cache.pipeline")
    async def test_xml_parsing(
        self,
        mock_async_cache_pipeline,
        mock_super_run,
        task,
        sample_zip_content,
    ):
        """Test parsing of Platforms.xml file"""
        mock_super_run.return_value = sample_zip_content

        # Create a mock pipeline with async context manager support
        mock_pipe = AsyncMock()
        mock_async_cache_pipeline.return_value.__aenter__ = AsyncMock(
            return_value=mock_pipe
        )
        mock_async_cache_pipeline.return_value.__aexit__ = AsyncMock(return_value=None)

        await task.run(force=True)

        # Verify calls
        assert mock_async_cache_pipeline.called
        assert mock_async_cache_pipeline.call_count == 4
        assert mock_pipe.hset.called
        assert mock_pipe.execute.called

        # Check hset call details
        hset_calls = mock_pipe.hset.call_args_list
        assert len(hset_calls) == 12

        platform_calls = [
            call for call in hset_calls if call[0][0] == LAUNCHBOX_PLATFORMS_KEY
        ]
        assert len(platform_calls) == 2

        metadata_id_calls = [
            call
            for call in hset_calls
            if call[0][0] == LAUNCHBOX_METADATA_DATABASE_ID_KEY
        ]
        metadata_name_calls = [
            call for call in hset_calls if call[0][0] == LAUNCHBOX_METADATA_NAME_KEY
        ]
        metadata_alt_calls = [
            call
            for call in hset_calls
            if call[0][0] == LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY
        ]
        metadata_image_calls = [
            call for call in hset_calls if call[0][0] == LAUNCHBOX_METADATA_IMAGE_KEY
        ]

        assert len(metadata_id_calls) == 2
        assert len(metadata_name_calls) == 2
        assert len(metadata_alt_calls) == 1
        assert len(metadata_image_calls) == 1

        mame_calls = [call for call in hset_calls if call[0][0] == LAUNCHBOX_MAME_KEY]
        assert len(mame_calls) == 2

        files_calls = [call for call in hset_calls if call[0][0] == LAUNCHBOX_FILES_KEY]
        assert len(files_calls) == 2

    @patch.object(RemoteFilePullTask, "run")
    @patch("tasks.scheduled.update_launchbox_metadata.async_cache.pipeline")
    async def test_empty_xml_elements_handling(
        self,
        mock_async_cache_pipeline,
        mock_super_run,
        task,
    ):
        """Test handling of XML elements with empty or missing text"""
        test_dir = os.path.dirname(__file__)
        sample_path = os.path.join(
            test_dir, "fixtures", "sample_metadata_with_empty_elements.zip"
        )

        async with await anyio.open_file(sample_path, "rb") as f:
            mock_super_run.return_value = await f.read()

        # Create a mock pipeline with async context manager support
        mock_pipe = AsyncMock()
        mock_async_cache_pipeline.return_value.__aenter__ = AsyncMock(
            return_value=mock_pipe
        )
        mock_async_cache_pipeline.return_value.__aexit__ = AsyncMock(return_value=None)

        await task.run(force=True)

        # Verify calls
        assert mock_async_cache_pipeline.called

        # Check hset call details
        hset_calls = mock_pipe.hset.call_args_list
        assert len(hset_calls) == 1

        platform_calls = [
            call for call in hset_calls if call[0][0] == LAUNCHBOX_PLATFORMS_KEY
        ]
        # Only one valid platform should be processed
        assert len(platform_calls) == 1

    @patch.object(RemoteFilePullTask, "run")
    @patch("tasks.scheduled.update_launchbox_metadata.async_cache.pipeline")
    async def test_missing_xml_files_handling(
        self,
        mock_async_cache_pipeline,
        mock_super_run,
        task,
    ):
        """Test handling when some XML files are missing from the ZIP"""
        test_dir = os.path.dirname(__file__)
        sample_path = os.path.join(
            test_dir, "fixtures", "sample_metadata_with_empty_elements.zip"
        )

        async with await anyio.open_file(sample_path, "rb") as f:
            mock_super_run.return_value = await f.read()

        # Create a mock pipeline with async context manager support
        mock_pipe = AsyncMock()
        mock_async_cache_pipeline.return_value.__aenter__ = AsyncMock(
            return_value=mock_pipe
        )
        mock_async_cache_pipeline.return_value.__aexit__ = AsyncMock(return_value=None)

        await task.run(force=True)

        # Verify calls
        assert mock_async_cache_pipeline.called

        # Check hset call details
        hset_calls = mock_pipe.hset.call_args_list
        assert len(hset_calls) == 1

    def test_redis_keys_are_defined(self):
        """Test that all Redis keys are properly defined"""
        assert LAUNCHBOX_PLATFORMS_KEY == "romm:launchbox_platforms"
        assert (
            LAUNCHBOX_METADATA_DATABASE_ID_KEY == "romm:launchbox_metadata_database_id"
        )
        assert LAUNCHBOX_METADATA_NAME_KEY == "romm:launchbox_metadata_name"
        assert (
            LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY
            == "romm:launchbox_metadata_alternate_name"
        )
        assert LAUNCHBOX_METADATA_IMAGE_KEY == "romm:launchbox_metadata_image"
        assert LAUNCHBOX_MAME_KEY == "romm:launchbox_mame"
        assert LAUNCHBOX_FILES_KEY == "romm:launchbox_files"

    def test_task_instance_creation(self):
        """Test that the task instance is created correctly"""
        assert isinstance(update_launchbox_metadata_task, UpdateLaunchboxMetadataTask)


class TestUpdateLaunchboxMetadataTaskIntegration:
    """Integration tests for UpdateLaunchboxMetadataTask"""

    @pytest.fixture
    def task(self):
        return UpdateLaunchboxMetadataTask()

    @patch.object(RemoteFilePullTask, "run")
    @patch("tasks.scheduled.update_launchbox_metadata.async_cache.pipeline")
    async def test_full_workflow_integration(
        self, mock_async_cache_pipeline, mock_super_run, task, sample_zip_content
    ):
        """Test the complete workflow from ZIP download to Redis storage"""
        mock_super_run.return_value = sample_zip_content

        # Create a mock pipeline with async context manager support
        mock_pipe = AsyncMock()
        mock_async_cache_pipeline.return_value.__aenter__ = AsyncMock(
            return_value=mock_pipe
        )
        mock_async_cache_pipeline.return_value.__aexit__ = AsyncMock(return_value=None)

        await task.run(force=True)

        # Check hset call details
        hset_calls = mock_pipe.hset.call_args_list
        assert len(hset_calls) == 12

        # Verify that all expected Redis keys were used
        redis_keys_used = [call[0][0] for call in hset_calls]

        expected_keys = [
            LAUNCHBOX_PLATFORMS_KEY,
            LAUNCHBOX_METADATA_DATABASE_ID_KEY,
            LAUNCHBOX_METADATA_NAME_KEY,
            LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY,
            LAUNCHBOX_METADATA_IMAGE_KEY,
            LAUNCHBOX_MAME_KEY,
            LAUNCHBOX_FILES_KEY,
        ]

        for expected_key in expected_keys:
            assert (
                expected_key in redis_keys_used
            ), f"Expected key {expected_key} not found in Redis operations"
