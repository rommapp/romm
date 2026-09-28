from logger.logger import log
from tasks.tasks import PeriodicTask, TaskType
from utils.install_cache import cleanup_expired_installs


class CleanupInstallCacheTask(PeriodicTask):
    def __init__(self) -> None:
        super().__init__(
            title="Scheduled install cache cleanup",
            description="Evicts install caches whose TTL has elapsed",
            task_type=TaskType.CLEANUP,
            enabled=True,
            manual_run=False,
            cron_string="0 4 * * *",
        )

    async def run(self) -> None:
        if not self.enabled:
            return

        evicted = cleanup_expired_installs()
        if evicted:
            log.info(f"Cleaned up {evicted} expired install caches")


cleanup_install_cache_task = CleanupInstallCacheTask()
