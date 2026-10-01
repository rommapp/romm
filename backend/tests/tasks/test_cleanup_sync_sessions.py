import tasks.scheduled.cleanup_sync_sessions as mod
from handler.database import db_sync_session_handler
from tasks.scheduled.cleanup_sync_sessions import CleanupSyncSessionsTask


class TestCleanupSyncSessionsTask:
    def test_default_schedule(self):
        task = CleanupSyncSessionsTask()
        assert task.enabled is True
        assert task.cron_string == "23 * * * *"

    def test_custom_schedule(self, monkeypatch):
        monkeypatch.setattr(mod, "SCHEDULED_CLEANUP_SYNC_SESSIONS_CRON", "0 2 * * *")
        assert CleanupSyncSessionsTask().cron_string == "0 2 * * *"

    async def test_disabled_cleanup_leaves_sessions_open(self, monkeypatch, mocker):
        monkeypatch.setattr(mod, "ENABLE_SCHEDULED_CLEANUP_SYNC_SESSIONS", False)
        fail_stale = mocker.patch.object(db_sync_session_handler, "fail_stale_sessions")
        task = CleanupSyncSessionsTask()
        assert task.enabled is False
        await task.run()
        fail_stale.assert_not_called()

    async def test_enabled_cleanup_fails_stale_sessions(self, mocker):
        fail_stale = mocker.patch.object(
            db_sync_session_handler, "fail_stale_sessions", return_value=2
        )
        await CleanupSyncSessionsTask().run()
        fail_stale.assert_called_once()
