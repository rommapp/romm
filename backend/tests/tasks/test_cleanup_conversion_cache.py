import os
import time

import pytest

from tasks.scheduled.cleanup_conversion_cache import CleanupConversionCacheTask
from utils import conversion_cache
from utils.conversion_cache import SENTINEL_NAME


class TestCleanupConversionCacheTask:
    def test_configuration(self):
        task = CleanupConversionCacheTask()
        assert task.enabled is True
        assert task.cron_string == "0 4 * * *"
        assert "cleanup_conversion_cache" in task.func

    async def test_run_calls_cleanup(self, mocker):
        task = CleanupConversionCacheTask()
        mock_cleanup = mocker.patch(
            "tasks.scheduled.cleanup_conversion_cache.cleanup_stale_conversions",
            return_value=2,
        )
        await task.run()
        mock_cleanup.assert_called_once_with()

    async def test_run_disabled_unschedules(self, mocker):
        task = CleanupConversionCacheTask()
        task.enabled = False
        mocker.patch.object(task, "unschedule")
        mock_cleanup = mocker.patch(
            "tasks.scheduled.cleanup_conversion_cache.cleanup_stale_conversions",
        )
        await task.run()
        mock_cleanup.assert_not_called()


class TestCleanupStaleConversions:
    @pytest.fixture
    def cache_root(self, tmp_path, mocker):
        mocker.patch.object(conversion_cache, "ROM_CONVERTO_CACHE_PATH", str(tmp_path))
        mocker.patch.object(
            conversion_cache.cm,
            "get_config",
            return_value=mocker.Mock(**{"CONVERTTO.cache_ttl_hours": 24}),
        )
        return tmp_path

    def test_missing_root_is_noop(self, tmp_path, mocker):
        mocker.patch.object(
            conversion_cache, "ROM_CONVERTO_CACHE_PATH", str(tmp_path / "nope")
        )
        assert conversion_cache.cleanup_stale_conversions() == 0

    def test_deletes_expired_and_keeps_fresh(self, cache_root):
        expired = cache_root / "1-a"
        expired.mkdir()
        (expired / "game.cia").write_bytes(b"x")
        old = time.time() - 25 * 3600
        os.utime(expired / "game.cia", (old, old))

        fresh = cache_root / "1-b"
        fresh.mkdir()
        (fresh / "game.cia").write_bytes(b"x")

        assert conversion_cache.cleanup_stale_conversions() == 1
        assert not expired.exists()
        assert fresh.exists()

    def test_deletes_stale_sentinel_only_dirs(self, cache_root):
        stale = cache_root / "1-c"
        stale.mkdir()
        sentinel = stale / SENTINEL_NAME
        sentinel.touch()
        old = time.time() - 7 * 3600
        os.utime(sentinel, (old, old))

        fresh = cache_root / "1-d"
        fresh.mkdir()
        (fresh / SENTINEL_NAME).touch()

        assert conversion_cache.cleanup_stale_conversions() == 1
        assert not stale.exists()
        assert fresh.exists()
