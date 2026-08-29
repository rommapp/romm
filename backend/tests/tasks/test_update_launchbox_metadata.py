import os
from unittest.mock import AsyncMock, patch

import anyio
import pytest

from config import TASK_TIMEOUT
from handler.metadata.launchbox_handler.handler import LaunchboxHandler
from handler.metadata.launchbox_handler.types import (
    LAUNCHBOX_FILES_KEY,
    LAUNCHBOX_MAME_KEY,
    LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY,
    LAUNCHBOX_METADATA_DATABASE_ID_KEY,
    LAUNCHBOX_METADATA_FOLDED_NAME_KEY,
    LAUNCHBOX_METADATA_IMAGE_KEY,
    LAUNCHBOX_METADATA_INITIAL_IMPORT_KEY,
    LAUNCHBOX_METADATA_NAME_KEY,
    LAUNCHBOX_PLATFORMS_KEY,
)
from handler.redis_handler import async_cache
from tasks.scheduled.update_launchbox_metadata import (
    BatchedCacheWriter,
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
        mocker.patch.object(LaunchboxHandler, "is_cloud_enabled", return_value=False)
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
        assert len(hset_calls) == 14

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
        metadata_folded_calls = [
            call
            for call in hset_calls
            if call[0][0] == LAUNCHBOX_METADATA_FOLDED_NAME_KEY
        ]

        assert len(metadata_id_calls) == 2
        assert len(metadata_name_calls) == 2
        assert len(metadata_alt_calls) == 1
        assert len(metadata_image_calls) == 1
        # Every named game is indexed under its folded title too.
        assert len(metadata_folded_calls) == len(metadata_name_calls)

        mame_calls = [call for call in hset_calls if call[0][0] == LAUNCHBOX_MAME_KEY]
        assert len(mame_calls) == 2

        files_calls = [call for call in hset_calls if call[0][0] == LAUNCHBOX_FILES_KEY]
        assert len(files_calls) == 2

        # The fixture pads one entry per index, as a pretty-printed dump does.
        # Keys come out normalized, and the Files key carries its platform,
        # since one dump filename exists on several systems.
        def fields(calls) -> set[str]:
            return {field for call in calls for field in call[1]["mapping"]}

        assert fields(files_calls) == {
            "super mario 64 (usa):Nintendo 64",
            "crash bandicoot (usa):PlayStation",
        }
        assert fields(platform_calls) == {"Nintendo 64", "PlayStation"}
        assert fields(metadata_id_calls) == {"12345", "67890"}
        assert fields(metadata_name_calls) == {
            "super mario 64:Nintendo 64",
            "crash bandicoot:PlayStation",
        }
        assert fields(metadata_alt_calls) == {"super mario 64 (usa)"}
        assert fields(metadata_image_calls) == {"12345"}
        assert fields(mame_calls) == {"mario.zip", "pacman.zip"}

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
        assert len(hset_calls) == 14

        # Verify that all expected Redis keys were used
        redis_keys_used = [call[0][0] for call in hset_calls]

        expected_keys = [
            LAUNCHBOX_PLATFORMS_KEY,
            LAUNCHBOX_METADATA_DATABASE_ID_KEY,
            LAUNCHBOX_METADATA_NAME_KEY,
            LAUNCHBOX_METADATA_FOLDED_NAME_KEY,
            LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY,
            LAUNCHBOX_METADATA_IMAGE_KEY,
            LAUNCHBOX_MAME_KEY,
            LAUNCHBOX_FILES_KEY,
        ]

        for expected_key in expected_keys:
            assert (
                expected_key in redis_keys_used
            ), f"Expected key {expected_key} not found in Redis operations"


class TestBatchedCacheWriter:
    """The dump is far too large to buffer into a single pipeline."""

    async def test_flushes_once_the_batch_is_full(self):
        pipe = AsyncMock()
        writer = BatchedCacheWriter(pipe, batch_size=3)

        for i in range(3):
            await writer.hset("key", f"field-{i}", {"i": i})

        assert pipe.execute.call_count == 1

    async def test_does_not_flush_a_partial_batch_early(self):
        pipe = AsyncMock()
        writer = BatchedCacheWriter(pipe, batch_size=3)

        await writer.hset("key", "field", {"a": 1})

        assert pipe.execute.call_count == 0

    async def test_final_flush_writes_the_remainder(self):
        pipe = AsyncMock()
        writer = BatchedCacheWriter(pipe, batch_size=3)

        await writer.hset("key", "field", {"a": 1})
        await writer.flush()

        assert pipe.execute.call_count == 1

    async def test_flush_is_a_noop_with_nothing_queued(self):
        pipe = AsyncMock()
        writer = BatchedCacheWriter(pipe, batch_size=3)

        await writer.flush()

        assert pipe.execute.call_count == 0

    async def test_values_are_json_encoded(self):
        pipe = AsyncMock()
        writer = BatchedCacheWriter(pipe, batch_size=10)

        await writer.hset("key", "field", {"Name": "Super Mario Bros."})

        pipe.hset.assert_called_once_with(
            "key", mapping={"field": '{"Name": "Super Mario Bros."}'}
        )

    async def test_large_input_flushes_repeatedly(self, task, sample_zip_content):
        """A real dump must not end up in one pipeline execute."""
        mock_pipe = AsyncMock()

        with (
            patch.object(RemoteFilePullTask, "run", return_value=sample_zip_content),
            patch(
                "tasks.scheduled.update_launchbox_metadata.CACHE_WRITE_BATCH_SIZE", 1
            ),
            patch(
                "tasks.scheduled.update_launchbox_metadata.async_cache.pipeline"
            ) as mock_pipeline,
        ):
            mock_pipeline.return_value.__aenter__ = AsyncMock(return_value=mock_pipe)
            mock_pipeline.return_value.__aexit__ = AsyncMock(return_value=None)

            await task.run(force=True)

        # One execute per queued write rather than one for the whole file.
        assert mock_pipe.execute.call_count == mock_pipe.hset.call_count


class TestInitialImportFlag:
    """The store is written in batches, so a half-filled one must not read as
    ready to the provider heartbeat."""

    @patch.object(RemoteFilePullTask, "run")
    @patch("tasks.scheduled.update_launchbox_metadata.async_cache.pipeline")
    async def test_first_import_flags_and_clears_on_completion(
        self, mock_pipeline, mock_super_run, task, sample_zip_content
    ):
        mock_super_run.return_value = sample_zip_content
        mock_pipeline.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
        mock_pipeline.return_value.__aexit__ = AsyncMock(return_value=None)

        with (
            patch.object(async_cache, "exists", AsyncMock(return_value=0)),
            patch.object(async_cache, "set", AsyncMock()) as mock_set,
            patch.object(async_cache, "delete", AsyncMock()) as mock_delete,
        ):
            await task.run(force=True)

        mock_set.assert_awaited_once_with(LAUNCHBOX_METADATA_INITIAL_IMPORT_KEY, "1")
        mock_delete.assert_awaited_once_with(LAUNCHBOX_METADATA_INITIAL_IMPORT_KEY)

    @patch.object(RemoteFilePullTask, "run")
    @patch("tasks.scheduled.update_launchbox_metadata.async_cache.pipeline")
    async def test_refresh_of_a_filled_store_is_not_flagged(
        self, mock_pipeline, mock_super_run, task, sample_zip_content
    ):
        """An existing store keeps answering while it is refreshed in place."""
        mock_super_run.return_value = sample_zip_content
        mock_pipeline.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
        mock_pipeline.return_value.__aexit__ = AsyncMock(return_value=None)

        with (
            patch.object(async_cache, "exists", AsyncMock(return_value=1)),
            patch.object(async_cache, "set", AsyncMock()) as mock_set,
            patch.object(async_cache, "delete", AsyncMock()),
        ):
            await task.run(force=True)

        mock_set.assert_not_awaited()

    @patch.object(RemoteFilePullTask, "run")
    async def test_flag_survives_a_failed_run(
        self, mock_super_run, task, corrupt_zip_content
    ):
        mock_super_run.return_value = corrupt_zip_content

        with (
            patch.object(async_cache, "exists", AsyncMock(return_value=0)),
            patch.object(async_cache, "set", AsyncMock()),
            patch.object(async_cache, "delete", AsyncMock()) as mock_delete,
        ):
            await task.run(force=True)

        mock_delete.assert_not_awaited()


class TestManualRunGate:
    def test_runnable_when_only_the_provider_is_enabled(self, task):
        """Enabling LaunchBox without the cron must still leave a way to fill
        the store, otherwise the provider silently matches nothing."""
        task.enabled = False
        with patch(
            "tasks.scheduled.update_launchbox_metadata.LAUNCHBOX_API_ENABLED", True
        ):
            assert task.can_run_manually is True

    def test_runnable_when_scheduled(self, task):
        task.enabled = True
        with patch(
            "tasks.scheduled.update_launchbox_metadata.LAUNCHBOX_API_ENABLED", False
        ):
            assert task.can_run_manually is True

    def test_not_runnable_when_launchbox_is_off(self, task):
        task.enabled = False
        with patch(
            "tasks.scheduled.update_launchbox_metadata.LAUNCHBOX_API_ENABLED", False
        ):
            assert task.can_run_manually is False

    def test_timeout_is_generous(self, task):
        """Downloading ~100MB and parsing ~500MB overruns the default timeout."""
        assert task.timeout >= 30 * 60
        assert task.timeout >= TASK_TIMEOUT
