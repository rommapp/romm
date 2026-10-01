import shutil
import time

from config import (
    ENABLE_SCHEDULED_CLEANUP_UPLOAD_TMP,
    ROM_UPLOAD_TMP_BASE,
    ROM_UPLOAD_TTL,
    SCHEDULED_CLEANUP_UPLOAD_TMP_CRON,
)
from logger.logger import log
from tasks.tasks import PeriodicTask, TaskType


class CleanupUploadTmpTask(PeriodicTask):
    def __init__(self) -> None:
        super().__init__(
            title="Scheduled upload tmp cleanup",
            description="Cleans up orphaned chunked-upload temp directories",
            task_type=TaskType.CLEANUP,
            enabled=ENABLE_SCHEDULED_CLEANUP_UPLOAD_TMP,
            manual_run=False,
            cron_string=SCHEDULED_CLEANUP_UPLOAD_TMP_CRON,
        )

    async def run(self) -> None:
        if not self.enabled:
            return

        if not ROM_UPLOAD_TMP_BASE.exists():
            return

        cutoff = time.time() - ROM_UPLOAD_TTL
        removed = 0

        for entry in ROM_UPLOAD_TMP_BASE.iterdir():
            if not entry.is_dir():
                continue
            try:
                if entry.stat().st_mtime < cutoff:
                    shutil.rmtree(entry, ignore_errors=True)
                    removed += 1
            except OSError:
                pass

        if removed:
            log.info(
                f"Cleaned up {removed} orphaned upload tmp director{'y' if removed == 1 else 'ies'}"
            )


cleanup_upload_tmp_task = CleanupUploadTmpTask()
