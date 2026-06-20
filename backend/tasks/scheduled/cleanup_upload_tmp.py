import shutil
import time

from endpoints.roms.upload import ROM_UPLOAD_TMP_BASE, ROM_UPLOAD_TTL
from logger.logger import log
from tasks.tasks import PeriodicTask, TaskType


class CleanupUploadTmpTask(PeriodicTask):
    def __init__(self):
        super().__init__(
            title="Scheduled upload tmp cleanup",
            description="Cleans up orphaned chunked-upload temp directories",
            task_type=TaskType.CLEANUP,
            enabled=True,
            manual_run=False,
            cron_string="0 * * * *",  # Every hour
            func="tasks.scheduled.cleanup_upload_tmp.cleanup_upload_tmp_task.run",
        )

    async def run(self) -> None:
        if not self.enabled:
            self.unschedule()
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
