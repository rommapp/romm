from datetime import datetime, timedelta, timezone

from handler.database import db_sync_session_handler
from logger.logger import log
from tasks.tasks import PeriodicTask, TaskType

# Longer than any launch: a session is opened before a game starts and closed
# after it exits, and a day of one sitting is not a session anyone is still in.
# Nothing else ever closes one, so without this a client that is killed, put to
# sleep or taken off the network leaves its row open for good.
STALE_AFTER_HOURS = 24


class CleanupSyncSessionsTask(PeriodicTask):
    def __init__(self):
        super().__init__(
            title="Scheduled sync session cleanup",
            description="Fails sync sessions no client ever completed",
            task_type=TaskType.CLEANUP,
            enabled=True,
            manual_run=False,
            cron_string="23 * * * *",  # Hourly, off the hour
        )

    async def run(self) -> None:
        if not self.enabled:
            return

        cutoff = datetime.now(timezone.utc) - timedelta(hours=STALE_AFTER_HOURS)
        failed = db_sync_session_handler.fail_stale_sessions(older_than=cutoff)
        if failed:
            log.info(f"Failed {failed} sync session(s) left open since {cutoff}")


cleanup_sync_sessions_task = CleanupSyncSessionsTask()
