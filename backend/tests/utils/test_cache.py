from unittest.mock import AsyncMock

from handler.metadata.base_hander import MAME_XML_KEY, METADATA_FIXTURES_DIR
from handler.redis_handler import async_cache
from redis.asyncio import Redis as AsyncRedis
from utils.cache import conditionally_set_cache


class TestConditionallySetCache:
    """Test the conditionally_set_cache function."""

    async def test_cache_not_exists_loads_data(self, mocker):
        """Test loading data when cache doesn't exist."""
        mock_cache_exists = mocker.patch.object(
            AsyncRedis, "exists", side_effect=AsyncMock(return_value=False)
        )
        mock_pipeline = AsyncMock()
        mock_cache_pipeline = mocker.patch.object(AsyncRedis, "pipeline")
        mock_cache_pipeline.return_value.__aenter__.return_value = mock_pipeline

        await conditionally_set_cache(
            async_cache, MAME_XML_KEY, METADATA_FIXTURES_DIR / "mame_index.json"
        )

        mock_cache_exists.assert_called_once_with(MAME_XML_KEY)
        mock_cache_pipeline.return_value.__aenter__.assert_called_once()
        mock_pipeline.hset.assert_called()
        mock_pipeline.execute.assert_called_once()

    async def test_cache_exists_skips_loading(self, mocker):
        """Test skipping load when cache already exists."""
        mock_cache_exists = mocker.patch.object(
            AsyncRedis, "exists", side_effect=AsyncMock(return_value=True)
        )
        mock_cache_pipeline = mocker.patch.object(AsyncRedis, "pipeline")

        await conditionally_set_cache(
            async_cache, MAME_XML_KEY, METADATA_FIXTURES_DIR / "mame_index.json"
        )

        mock_cache_exists.assert_called_once_with(MAME_XML_KEY)
        mock_cache_pipeline.assert_not_called()

    async def test_exception_handling(self, mocker):
        """Test exception handling when file loading fails."""
        mocker.patch.object(
            AsyncRedis, "exists", side_effect=AsyncMock(return_value=False)
        )
        mock_cache_pipeline = mocker.patch.object(AsyncRedis, "pipeline")

        await conditionally_set_cache(
            async_cache, MAME_XML_KEY, METADATA_FIXTURES_DIR / "nonexistent.json"
        )

        mock_cache_pipeline.assert_not_called()
