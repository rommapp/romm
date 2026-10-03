from dataclasses import replace

from handler.database import db_sync_session_handler
from tasks.registry import CLEANUP_SYNC_SESSIONS_SPEC
from tasks.scheduled.cleanup_sync_sessions import CleanupSyncSessionsTask


class TestCleanupSyncSessionsTask:
    def test_default_schedule(self):
        assert CLEANUP_SYNC_SESSIONS_SPEC.enabled is True
        assert CLEANUP_SYNC_SESSIONS_SPEC.cron_string == "23 * * * *"

    async def test_disabled_cleanup_leaves_sessions_open(self, mocker):
        fail_stale = mocker.patch.object(db_sync_session_handler, "fail_stale_sessions")
        task = CleanupSyncSessionsTask()
        task.spec = replace(task.spec, enabled=False)
        await task.run()
        fail_stale.assert_not_called()

    async def test_enabled_cleanup_fails_stale_sessions(self, mocker):
        fail_stale = mocker.patch.object(
            db_sync_session_handler, "fail_stale_sessions", return_value=2
        )
        await CleanupSyncSessionsTask().run()
        fail_stale.assert_called_once()
