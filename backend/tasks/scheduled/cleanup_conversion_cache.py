from logger.logger import log
from tasks.tasks import PeriodicTask, TaskType
from utils.conversion_cache import cleanup_stale_conversions


class CleanupConversionCacheTask(PeriodicTask):
    def __init__(self):
        super().__init__(
            title="Scheduled conversion cache cleanup",
            description="Removes stale converted download files based on TTL",
            task_type=TaskType.CLEANUP,
            enabled=True,
            manual_run=False,
            cron_string="0 4 * * *",
        )

    async def run(self) -> None:
        if not self.enabled:
            return

        deleted = cleanup_stale_conversions()
        if deleted:
            log.info(f"Cleaned up {deleted} stale converted download caches")


cleanup_conversion_cache_task = CleanupConversionCacheTask()
