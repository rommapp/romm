from tasks.scheduled.cleanup_zip_cache import CleanupZipCacheTask


class TestCleanupZipCacheTask:
    def test_configuration(self):
        task = CleanupZipCacheTask()
        assert task.enabled is True
        assert task.cron_string == "0 4 * * *"

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
