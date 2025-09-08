import json
from unittest.mock import AsyncMock, patch

import pytest

from tasks.scheduled.update_switch_titledb import (
    SWITCH_PRODUCT_ID_KEY,
    SWITCH_TITLEDB_INDEX_KEY,
    UpdateSwitchTitleDBTask,
    update_switch_titledb_task,
)
from tasks.tasks import RemoteFilePullTask


class TestUpdateSwitchTitleDBTask:
    @pytest.fixture
    def task(self):
        return UpdateSwitchTitleDBTask()

    @pytest.fixture
    def sample_titledb_data(self):
        return {
            "0100000000010000": {
                "id": "0100000000010000",
                "name": "Super Mario Odyssey",
                "publisher": "Nintendo",
                "region": "US",
                "version": "1.3.0",
            },
            "0100000000020000": {
                "id": "0100000000020000",
                "name": "The Legend of Zelda: Breath of the Wild",
                "publisher": "Nintendo",
                "region": "US",
                "version": "1.6.0",
            },
            "0100000000030000": {
                "id": "0100000000030000",
                "name": "Mario Kart 8 Deluxe",
                "publisher": "Nintendo",
                "region": "US",
                "version": "2.1.0",
            },
            "": {  # Empty key to test filtering
                "id": "should_be_filtered",
                "name": "Should not appear",
            },
            "0100000000040000": None,  # None value to test filtering
        }

    @pytest.fixture
    def sample_json_content(self, sample_titledb_data):
        return json.dumps(sample_titledb_data).encode("utf-8")

    def test_init(self, task):
        """Test task initialization"""
        assert (
            task.func
            == "tasks.scheduled.update_switch_titledb.update_switch_titledb_task.run"
        )
        assert task.description == "Updates the Nintendo Switch TitleDB file"
        assert (
            task.url
            == "https://raw.githubusercontent.com/blawar/titledb/master/US.en.json"
        )

    @patch.object(RemoteFilePullTask, "run")
    @patch("tasks.scheduled.update_switch_titledb.async_cache.pipeline")
    async def test_run_success(
        self,
        mock_async_cache_pipeline,
        mock_super_run,
        task,
        sample_json_content,
    ):
        """Test successful run with valid data"""
        mock_super_run.return_value = sample_json_content

        # Create mock pipeline with async context manager support
        mock_pipe = AsyncMock()
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=None)
        mock_async_cache_pipeline.return_value = mock_pipe

        await task.run(force=True)

        # Verify super().run was called
        mock_super_run.assert_called_once_with(True)

        # Verify pipeline was used
        assert mock_async_cache_pipeline.called
        assert mock_pipe.hset.called
        assert mock_pipe.execute.called

        # Verify hset was called for both keys
        hset_calls = mock_pipe.hset.call_args_list

        # Should have calls for both SWITCH_TITLEDB_INDEX_KEY and SWITCH_PRODUCT_ID_KEY
        titledb_calls = [
            call for call in hset_calls if call[0][0] == SWITCH_TITLEDB_INDEX_KEY
        ]
        product_calls = [
            call for call in hset_calls if call[0][0] == SWITCH_PRODUCT_ID_KEY
        ]

        assert len(titledb_calls) > 0
        assert len(product_calls) > 0

    @patch.object(RemoteFilePullTask, "run")
    @patch("tasks.scheduled.update_switch_titledb.async_cache.pipeline")
    async def test_run_filters_empty_data(
        self,
        mock_async_cache_pipeline,
        mock_super_run,
        task,
        sample_json_content,
    ):
        """Test that empty keys and None values are filtered out"""
        mock_super_run.return_value = sample_json_content

        mock_pipe = AsyncMock()
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=None)
        mock_async_cache_pipeline.return_value = mock_pipe

        await task.run(force=True)

        # Get all the mapping data that was passed to hset
        hset_calls = mock_pipe.hset.call_args_list

        for call in hset_calls:
            args, kwargs = call
            if "mapping" in kwargs:
                mapping = kwargs["mapping"]
                # Verify no empty keys
                assert "" not in mapping
                # Verify no None values in the original data structure
                for key in mapping.keys():
                    assert key is not None and key != ""

    @patch.object(RemoteFilePullTask, "run")
    @patch("tasks.scheduled.update_switch_titledb.async_cache.pipeline")
    async def test_run_batches_data(
        self,
        mock_async_cache_pipeline,
        mock_super_run,
        task,
    ):
        """Test that data is properly batched"""
        # Create a large dataset to test batching
        large_dataset = {}
        for i in range(5000):  # More than 2000 to ensure batching
            large_dataset[f"010000000{i:07d}"] = {
                "id": f"010000000{i:07d}",
                "name": f"Game {i}",
                "publisher": "Test Publisher",
            }

        large_json_content = json.dumps(large_dataset).encode("utf-8")
        mock_super_run.return_value = large_json_content

        mock_pipe = AsyncMock()
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=None)
        mock_async_cache_pipeline.return_value = mock_pipe

        await task.run(force=True)

        # Should have multiple hset calls due to batching
        hset_calls = mock_pipe.hset.call_args_list
        assert len(hset_calls) > 2  # At least one batch for each key type

    @patch.object(RemoteFilePullTask, "run")
    async def test_run_no_content(self, mock_super_run, task):
        """Test run when super().run returns None"""
        mock_super_run.return_value = None

        await task.run(force=True)

        # Should return early without doing anything
        mock_super_run.assert_called_once_with(True)

    @patch.object(RemoteFilePullTask, "run")
    @patch("tasks.scheduled.update_switch_titledb.async_cache.pipeline")
    async def test_run_invalid_json(
        self,
        mock_async_cache_pipeline,
        mock_super_run,
        task,
    ):
        """Test run with invalid JSON content"""
        mock_super_run.return_value = b"invalid json content"

        with pytest.raises(json.JSONDecodeError):
            await task.run(force=True)

    @patch.object(RemoteFilePullTask, "run")
    @patch("tasks.scheduled.update_switch_titledb.async_cache.pipeline")
    async def test_run_empty_json(
        self,
        mock_async_cache_pipeline,
        mock_super_run,
        task,
    ):
        """Test run with empty JSON object"""
        mock_super_run.return_value = json.dumps({}).encode("utf-8")

        mock_pipe = AsyncMock()
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=None)
        mock_async_cache_pipeline.return_value = mock_pipe

        await task.run(force=True)

        # Should still call execute even with empty data
        assert mock_pipe.execute.called

    @patch.object(RemoteFilePullTask, "run")
    @patch("tasks.scheduled.update_switch_titledb.async_cache.pipeline")
    async def test_product_id_mapping(
        self,
        mock_async_cache_pipeline,
        mock_super_run,
        task,
        sample_json_content,
    ):
        """Test that product ID mapping works correctly"""
        mock_super_run.return_value = sample_json_content

        mock_pipe = AsyncMock()
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=None)
        mock_async_cache_pipeline.return_value = mock_pipe

        await task.run(force=True)

        # Find product ID calls
        hset_calls = mock_pipe.hset.call_args_list
        product_calls = [
            call for call in hset_calls if call[0][0] == SWITCH_PRODUCT_ID_KEY
        ]

        assert len(product_calls) > 0

        # Verify product mapping structure
        for call in product_calls:
            args, kwargs = call
            if "mapping" in kwargs:
                mapping = kwargs["mapping"]
                for product_id, data_json in mapping.items():
                    data = json.loads(data_json)
                    assert data.get("id") == product_id

    @patch.object(RemoteFilePullTask, "run")
    @patch("tasks.scheduled.update_switch_titledb.async_cache.pipeline")
    @patch("tasks.scheduled.update_switch_titledb.log")
    async def test_completion_log(
        self,
        mock_log,
        mock_async_cache_pipeline,
        mock_super_run,
        task,
        sample_json_content,
    ):
        """Test that completion is logged"""
        mock_super_run.return_value = sample_json_content

        mock_pipe = AsyncMock()
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=None)
        mock_async_cache_pipeline.return_value = mock_pipe

        await task.run(force=True)

        mock_log.info.assert_called_with("Scheduled switch titledb update completed!")

    def test_task_instance(self):
        """Test that the module-level task instance is created correctly"""
        assert isinstance(update_switch_titledb_task, UpdateSwitchTitleDBTask)
        assert (
            update_switch_titledb_task.url
            == "https://raw.githubusercontent.com/blawar/titledb/master/US.en.json"
        )
