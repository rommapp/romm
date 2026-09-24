from tasks.scheduled.cleanup_conversion_cache import CleanupConversionCacheTask


class TestCleanupConversionCacheTask:
    def test_configuration(self):
        task = CleanupConversionCacheTask()
        assert task.enabled is True
        assert task.cron_string == "0 4 * * *"

    async def test_run_calls_cleanup(self, mocker):
        task = CleanupConversionCacheTask()
        mock_cleanup = mocker.patch(
            "tasks.scheduled.cleanup_conversion_cache.cleanup_stale_conversions",
            return_value=2,
        )
        await task.run()
        mock_cleanup.assert_called_once_with()

    async def test_run_disabled_skips_the_cleanup(self, mocker):
        task = CleanupConversionCacheTask()
        task.enabled = False
        mock_cleanup = mocker.patch(
            "tasks.scheduled.cleanup_conversion_cache.cleanup_stale_conversions",
        )
        await task.run()
        mock_cleanup.assert_not_called()
