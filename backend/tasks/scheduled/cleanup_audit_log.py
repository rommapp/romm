from datetime import datetime, timedelta, timezone
from typing import Final

from config import AUDIT_LOG_RETENTION_DAYS
from handler.database import db_audit_event_handler
from logger.logger import log
from tasks.registry import CLEANUP_AUDIT_LOG_SPEC
from tasks.tasks import PeriodicTask

# Each batch is its own short transaction, so the table stays writable meanwhile.
DELETE_BATCH_SIZE: Final = 5000


class CleanupAuditLogTask(PeriodicTask):
    def __init__(self) -> None:
        super().__init__(CLEANUP_AUDIT_LOG_SPEC)

    async def run(self) -> int:
        if not self.spec.enabled:
            return 0

        cutoff = datetime.now(timezone.utc) - timedelta(days=AUDIT_LOG_RETENTION_DAYS)
        deleted = 0
        while True:
            batch = db_audit_event_handler.delete_batch_before(
                cutoff, DELETE_BATCH_SIZE
            )
            deleted += batch
            if batch < DELETE_BATCH_SIZE:
                break
        if deleted:
            log.info(f"Removed {deleted} audit log events older than {cutoff}")
        return deleted


cleanup_audit_log_task = CleanupAuditLogTask()
