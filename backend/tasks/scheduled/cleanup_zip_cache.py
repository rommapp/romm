from logger.logger import log
from tasks.tasks import PeriodicTask, TaskType
from utils.zip_cache import cleanup_stale_zips


class CleanupZipCacheTask(PeriodicTask):
    def __init__(self):
        super().__init__(
            title="Scheduled ZIP cache cleanup",
            description="Removes cached ZIP files older than 48 hours",
            task_type=TaskType.CLEANUP,
            enabled=True,
            manual_run=False,
            cron_string="0 4 * * *",  # Daily at 4 AM
            func="tasks.scheduled.cleanup_zip_cache.cleanup_zip_cache_task.run",
        )

    async def run(self) -> None:
        if not self.enabled:
            self.unschedule()
            return

        deleted = cleanup_stale_zips(max_age_hours=48)
        if deleted:
            log.info(f"Cleaned up {deleted} stale cached ZIP files")


cleanup_zip_cache_task = CleanupZipCacheTask()
