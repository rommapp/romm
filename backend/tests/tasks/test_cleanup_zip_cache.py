import tasks.scheduled.cleanup_zip_cache as mod
from tasks.scheduled.cleanup_zip_cache import CleanupZipCacheTask


class TestCleanupZipCacheTask:
    def test_configuration(self):
        task = CleanupZipCacheTask()
        assert task.enabled is True
        assert task.cron_string == "0 4 * * *"

    def test_custom_schedule(self, monkeypatch):
        monkeypatch.setattr(mod, "SCHEDULED_CLEANUP_ZIP_CACHE_CRON", "0 2 * * *")
        assert CleanupZipCacheTask().cron_string == "0 2 * * *"

    def test_disabled_by_env(self, monkeypatch):
        monkeypatch.setattr(mod, "ENABLE_SCHEDULED_CLEANUP_ZIP_CACHE", False)
        assert CleanupZipCacheTask().enabled is False

    async def test_run_calls_cleanup(self, mocker):
        task = CleanupZipCacheTask()
        mock_cleanup = mocker.patch(
            "tasks.scheduled.cleanup_zip_cache.cleanup_stale_zips",
            return_value=3,
        )
        await task.run()
        mock_cleanup.assert_called_once_with()

    async def test_run_disabled_skips_the_cleanup(self, mocker):
        task = CleanupZipCacheTask()
        task.enabled = False
        mock_cleanup = mocker.patch(
            "tasks.scheduled.cleanup_zip_cache.cleanup_stale_zips",
        )
        await task.run()
        mock_cleanup.assert_not_called()
