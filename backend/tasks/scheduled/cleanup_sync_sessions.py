from datetime import datetime, timedelta, timezone

from handler.database import db_sync_session_handler
from logger.logger import log
from tasks.registry import CLEANUP_SYNC_SESSIONS_SPEC
from tasks.tasks import PeriodicTask

# Longer than any launch, since nothing else closes a session: one killed, put
# to sleep or taken off the network would otherwise stay open for good.
STALE_AFTER_HOURS = 24


class CleanupSyncSessionsTask(PeriodicTask):
    def __init__(self) -> None:
        super().__init__(CLEANUP_SYNC_SESSIONS_SPEC)

    async def run(self) -> None:
        if not self.spec.enabled:
            return

        cutoff = datetime.now(timezone.utc) - timedelta(hours=STALE_AFTER_HOURS)
        failed = db_sync_session_handler.fail_stale_sessions(older_than=cutoff)
        if failed:
            log.info(f"Failed {failed} sync session(s) left open since {cutoff}")


cleanup_sync_sessions_task = CleanupSyncSessionsTask()
