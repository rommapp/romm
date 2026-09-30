from config import ENABLE_SCHEDULED_CLEANUP_ZIP_CACHE, SCHEDULED_CLEANUP_ZIP_CACHE_CRON
from logger.logger import log
from tasks.tasks import PeriodicTask, TaskType
from utils.zip_cache import cleanup_stale_zips


class CleanupZipCacheTask(PeriodicTask):
    def __init__(self) -> None:
        super().__init__(
            title="Scheduled ZIP cache cleanup",
            description="Removes stale cached ZIP files based on tiered TTL",
            task_type=TaskType.CLEANUP,
            enabled=ENABLE_SCHEDULED_CLEANUP_ZIP_CACHE,
            manual_run=False,
            cron_string=SCHEDULED_CLEANUP_ZIP_CACHE_CRON,
        )

    async def run(self) -> None:
        if not self.enabled:
            return

        deleted = cleanup_stale_zips()
        if deleted:
            log.info(f"Cleaned up {deleted} stale cached ZIP files")


cleanup_zip_cache_task = CleanupZipCacheTask()
