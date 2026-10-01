from logger.logger import log
from tasks.registry import CLEANUP_ZIP_CACHE_SPEC
from tasks.tasks import PeriodicTask
from utils.zip_cache import cleanup_stale_zips


class CleanupZipCacheTask(PeriodicTask):
    def __init__(self) -> None:
        super().__init__(CLEANUP_ZIP_CACHE_SPEC)

    async def run(self) -> None:
        if not self.spec.enabled:
            return

        deleted = cleanup_stale_zips()
        if deleted:
            log.info(f"Cleaned up {deleted} stale cached ZIP files")


cleanup_zip_cache_task = CleanupZipCacheTask()
