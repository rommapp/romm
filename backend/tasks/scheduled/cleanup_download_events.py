"""Background task to age out rows from the download event log."""

from datetime import datetime, timedelta, timezone

from config import (
    DOWNLOAD_EVENTS_RETENTION_DAYS,
    SCHEDULED_CLEANUP_DOWNLOAD_EVENTS_CRON,
)
from handler.database import db_download_handler
from logger.logger import log
from tasks.tasks import PeriodicTask, TaskType


class CleanupDownloadEventsTask(PeriodicTask):
    """Trims `download_events` to the configured retention window.

    Off by default: the log is an audit trail, so it only shrinks when an
    admin sets `DOWNLOAD_EVENTS_RETENTION_DAYS`. Per-rom counters are lifetime
    totals and are never rewritten by this task.
    """

    def __init__(self):
        super().__init__(
            title="Scheduled download log cleanup",
            description=(
                "Deletes download log entries older than "
                "DOWNLOAD_EVENTS_RETENTION_DAYS"
            ),
            task_type=TaskType.CLEANUP,
            enabled=DOWNLOAD_EVENTS_RETENTION_DAYS > 0,
            manual_run=True,
            cron_string=SCHEDULED_CLEANUP_DOWNLOAD_EVENTS_CRON,
            func="tasks.scheduled.cleanup_download_events.cleanup_download_events_task.run",
        )

    async def run(self) -> None:
        if not self.enabled or DOWNLOAD_EVENTS_RETENTION_DAYS <= 0:
            self.unschedule()
            return

        cutoff = datetime.now(timezone.utc) - timedelta(
            days=DOWNLOAD_EVENTS_RETENTION_DAYS
        )
        deleted = db_download_handler.prune_events_older_than(cutoff)

        if deleted:
            log.info(
                f"Pruned {deleted} download log "
                f"{'entry' if deleted == 1 else 'entries'} older than "
                f"{DOWNLOAD_EVENTS_RETENTION_DAYS} days"
            )


cleanup_download_events_task = CleanupDownloadEventsTask()
