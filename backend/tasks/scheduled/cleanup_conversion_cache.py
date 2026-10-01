from logger.logger import log
from tasks.registry import CLEANUP_CONVERSION_CACHE_SPEC
from tasks.tasks import PeriodicTask
from utils.conversion_cache import cleanup_stale_conversions


class CleanupConversionCacheTask(PeriodicTask):
    def __init__(self) -> None:
        super().__init__(CLEANUP_CONVERSION_CACHE_SPEC)

    async def run(self) -> None:
        if not self.spec.enabled:
            return

        deleted = cleanup_stale_conversions()
        if deleted:
            log.info(f"Cleaned up {deleted} stale converted download caches")


cleanup_conversion_cache_task = CleanupConversionCacheTask()
