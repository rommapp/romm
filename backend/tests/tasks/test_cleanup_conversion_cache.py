from dataclasses import replace

from tasks.registry import CLEANUP_CONVERSION_CACHE_SPEC
from tasks.scheduled.cleanup_conversion_cache import CleanupConversionCacheTask


class TestCleanupConversionCacheTask:
    def test_configuration(self):
        assert CLEANUP_CONVERSION_CACHE_SPEC.enabled is True
        assert CLEANUP_CONVERSION_CACHE_SPEC.cron_string == "0 4 * * *"

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
        task.spec = replace(task.spec, enabled=False)
        mock_cleanup = mocker.patch(
            "tasks.scheduled.cleanup_conversion_cache.cleanup_stale_conversions",
        )
        await task.run()
        mock_cleanup.assert_not_called()
