from datetime import datetime, timedelta, timezone

from handler.database import db_audit_event_handler
from tasks.scheduled import cleanup_audit_log
from tasks.scheduled.cleanup_audit_log import CleanupAuditLogTask


class TestCleanupAuditLogTask:
    def test_runs_daily_when_events_expire(self, mocker):
        mocker.patch.object(cleanup_audit_log, "AUDIT_LOG_RETENTION_DAYS", 90)
        task = CleanupAuditLogTask()

        assert task.enabled is True
        assert task.cron_string == "30 4 * * *"

    def test_is_off_when_events_are_kept_forever(self, mocker):
        mocker.patch.object(cleanup_audit_log, "AUDIT_LOG_RETENTION_DAYS", 0)

        assert CleanupAuditLogTask().enabled is False

    async def test_deletes_batches_until_one_comes_back_short(self, mocker):
        mocker.patch.object(cleanup_audit_log, "AUDIT_LOG_RETENTION_DAYS", 90)
        mocker.patch.object(cleanup_audit_log, "DELETE_BATCH_SIZE", 2)
        delete = mocker.patch.object(
            db_audit_event_handler,
            "delete_batch_before",
            side_effect=[2, 2, 1],
        )
        task = CleanupAuditLogTask()

        deleted = await task.run()

        assert deleted == 5
        assert delete.call_count == 3
        cutoff = delete.call_args.args[0]
        expected = datetime.now(timezone.utc) - timedelta(days=90)
        assert abs(cutoff - expected) < timedelta(minutes=1)

    async def test_run_disabled_skips_the_cleanup(self, mocker):
        delete = mocker.patch.object(db_audit_event_handler, "delete_batch_before")
        task = CleanupAuditLogTask()
        task.enabled = False

        assert await task.run() == 0
        delete.assert_not_called()
