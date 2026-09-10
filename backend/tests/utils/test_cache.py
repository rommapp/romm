from unittest.mock import AsyncMock

import pytest

from handler.metadata.base_handler import MAME_XML_KEY, METADATA_FIXTURES_DIR
from handler.redis_handler import async_cache
from utils.cache import (
    conditionally_set_cache,
    drop_stale_cache_store,
    is_cache_schema_current,
    stamp_cache_schema,
)


class TestConditionallySetCache:
    """Test the conditionally_set_cache function."""

    async def test_cache_not_exists_loads_data(self, mocker):
        """Test loading data when cache doesn't exist."""
        mock_cache_exists = mocker.patch.object(
            async_cache, "exists", new_callable=AsyncMock, return_value=False
        )
        mock_pipeline = AsyncMock()
        mock_cache_pipeline = mocker.patch.object(async_cache, "pipeline")
        mock_cache_pipeline.return_value.__aenter__.return_value = mock_pipeline

        await conditionally_set_cache(
            async_cache, MAME_XML_KEY, METADATA_FIXTURES_DIR / "mame_index.json"
        )

        mock_cache_exists.assert_called_once_with(MAME_XML_KEY)
        mock_cache_pipeline.return_value.__aenter__.assert_called_once()
        mock_pipeline.hset.assert_called()
        mock_pipeline.execute.assert_called_once()

    async def test_cache_exists_and_hash_does_not_match_loads_data(self, mocker):
        """Test loading data when cache exists but file hash does not match."""
        mock_cache_exists = mocker.patch.object(
            async_cache, "exists", new_callable=AsyncMock, return_value=True
        )
        mock_pipeline = AsyncMock()
        mock_cache_pipeline = mocker.patch.object(async_cache, "pipeline")
        mock_cache_pipeline.return_value.__aenter__.return_value = mock_pipeline

        await conditionally_set_cache(
            async_cache, MAME_XML_KEY, METADATA_FIXTURES_DIR / "mame_index.json"
        )

        mock_cache_exists.assert_called_once_with(MAME_XML_KEY)
        mock_cache_pipeline.return_value.__aenter__.assert_called_once()
        mock_pipeline.hset.assert_called()
        mock_pipeline.execute.assert_called_once()

    async def test_cache_exists_and_hash_matches_skips_loading(self, mocker):
        """Test skipping load when cache already exists and file hash matches."""
        fake_md5_hash = "d41d8cd98f00b204e9800998ecf8427e"
        mocker.patch(
            "hashlib.md5",
            return_value=AsyncMock(
                hexdigest=lambda: fake_md5_hash,
                update=lambda x: None,
            ),
        )
        mock_cache_exists = mocker.patch.object(
            async_cache, "exists", new_callable=AsyncMock, return_value=True
        )
        mock_cache_get = mocker.patch.object(
            async_cache, "get", new_callable=AsyncMock, return_value=fake_md5_hash
        )
        mock_cache_pipeline = mocker.patch.object(async_cache, "pipeline")

        await conditionally_set_cache(
            async_cache, MAME_XML_KEY, METADATA_FIXTURES_DIR / "mame_index.json"
        )

        mock_cache_exists.assert_called_once_with(MAME_XML_KEY)
        mock_cache_get.assert_called_once_with(f"{MAME_XML_KEY}:file_hash")
        mock_cache_pipeline.assert_not_called()

    async def test_exception_handling(self, mocker):
        """Test exception handling when file loading fails."""
        mocker.patch.object(
            async_cache, "exists", new_callable=AsyncMock, return_value=False
        )
        mock_cache_pipeline = mocker.patch.object(async_cache, "pipeline")

        await conditionally_set_cache(
            async_cache, MAME_XML_KEY, METADATA_FIXTURES_DIR / "nonexistent.json"
        )

        mock_cache_pipeline.assert_not_called()


class TestCacheSchema:
    """A store is read only while its stamp matches the readers' shape."""

    async def test_matching_stamp_is_current(self, mocker):
        mocker.patch.object(
            async_cache, "get", new_callable=AsyncMock, return_value="2"
        )

        assert (
            await is_cache_schema_current(async_cache, "romm:store_schema", 2) is True
        )

    @pytest.mark.parametrize("stamped", [None, "1", "not-a-version"])
    async def test_other_stamps_are_stale(self, mocker, stamped: str | None):
        mocker.patch.object(
            async_cache, "get", new_callable=AsyncMock, return_value=stamped
        )

        assert (
            await is_cache_schema_current(async_cache, "romm:store_schema", 2) is False
        )

    async def test_stamp_records_the_version(self, mocker):
        mock_set = mocker.patch.object(async_cache, "set", new_callable=AsyncMock)

        await stamp_cache_schema(async_cache, "romm:store_schema", 2)

        mock_set.assert_awaited_once_with("romm:store_schema", "2")

    async def test_stale_store_is_dropped_with_its_stamp(self, mocker):
        mocker.patch.object(
            async_cache, "get", new_callable=AsyncMock, return_value="1"
        )
        mocker.patch.object(
            async_cache, "exists", new_callable=AsyncMock, return_value=1
        )
        mock_delete = mocker.patch.object(async_cache, "delete", new_callable=AsyncMock)

        dropped = await drop_stale_cache_store(
            async_cache, "romm:store_schema", 2, ("romm:a", "romm:b")
        )

        assert dropped is True
        mock_delete.assert_awaited_once_with("romm:a", "romm:b", "romm:store_schema")

    async def test_current_store_is_left_alone(self, mocker):
        mocker.patch.object(
            async_cache, "get", new_callable=AsyncMock, return_value="2"
        )
        mock_delete = mocker.patch.object(async_cache, "delete", new_callable=AsyncMock)

        dropped = await drop_stale_cache_store(
            async_cache, "romm:store_schema", 2, ("romm:a",)
        )

        assert dropped is False
        mock_delete.assert_not_awaited()

    async def test_store_that_was_never_filled_is_not_a_drop(self, mocker):
        """An install that never imported has nothing to rebuild."""
        mocker.patch.object(
            async_cache, "get", new_callable=AsyncMock, return_value=None
        )
        mocker.patch.object(
            async_cache, "exists", new_callable=AsyncMock, return_value=0
        )
        mock_delete = mocker.patch.object(async_cache, "delete", new_callable=AsyncMock)

        dropped = await drop_stale_cache_store(
            async_cache, "romm:store_schema", 2, ("romm:a",)
        )

        assert dropped is False
        mock_delete.assert_not_awaited()
