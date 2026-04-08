import pytest
from sqlalchemy.exc import NoResultFound

from handler.database import db_device_handler, db_sync_session_handler
from models.device import Device
from models.sync_session import SyncSessionStatus
from models.user import User


class TestCreateSession:
    def test_creates_pending_session(self, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="sess-dev-1", user_id=admin_user.id)
        )
        session = db_sync_session_handler.create_session(device.id, admin_user.id)

        assert session.id is not None
        assert session.device_id == device.id
        assert session.user_id == admin_user.id
        assert session.status == SyncSessionStatus.PENDING
        assert session.initiated_at is not None
        assert session.completed_at is None


class TestGetSession:
    def test_get_existing_session(self, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="get-dev-1", user_id=admin_user.id)
        )
        created = db_sync_session_handler.create_session(device.id, admin_user.id)

        result = db_sync_session_handler.get_session(created.id, admin_user.id)
        assert result is not None
        assert result.id == created.id

    def test_get_session_wrong_user(self, admin_user: User, editor_user: User):
        device = db_device_handler.add_device(
            Device(id="get-dev-2", user_id=admin_user.id)
        )
        created = db_sync_session_handler.create_session(device.id, admin_user.id)

        result = db_sync_session_handler.get_session(created.id, editor_user.id)
        assert result is None

    def test_get_nonexistent_session(self, admin_user: User):
        result = db_sync_session_handler.get_session(999999, admin_user.id)
        assert result is None


class TestGetActiveSession:
    def test_returns_pending_session(self, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="active-dev-1", user_id=admin_user.id)
        )
        created = db_sync_session_handler.create_session(device.id, admin_user.id)

        result = db_sync_session_handler.get_active_session(device.id, admin_user.id)
        assert result is not None
        assert result.id == created.id

    def test_returns_in_progress_session(self, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="active-dev-2", user_id=admin_user.id)
        )
        created = db_sync_session_handler.create_session(device.id, admin_user.id)
        db_sync_session_handler.update_session(
            created.id, {"status": SyncSessionStatus.IN_PROGRESS}
        )

        result = db_sync_session_handler.get_active_session(device.id, admin_user.id)
        assert result is not None
        assert result.status == SyncSessionStatus.IN_PROGRESS

    def test_does_not_return_completed_session(self, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="active-dev-3", user_id=admin_user.id)
        )
        created = db_sync_session_handler.create_session(device.id, admin_user.id)
        db_sync_session_handler.complete_session(created.id)

        result = db_sync_session_handler.get_active_session(device.id, admin_user.id)
        assert result is None

    def test_no_active_session(self, admin_user: User):
        result = db_sync_session_handler.get_active_session(
            "nonexistent", admin_user.id
        )
        assert result is None


class TestCompleteSession:
    def test_marks_completed_with_counts(self, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="comp-dev-1", user_id=admin_user.id)
        )
        created = db_sync_session_handler.create_session(device.id, admin_user.id)

        result = db_sync_session_handler.complete_session(
            created.id, operations_completed=10, operations_failed=2
        )
        assert result.status == SyncSessionStatus.COMPLETED
        assert result.operations_completed == 10
        assert result.operations_failed == 2
        assert result.completed_at is not None


class TestFailSession:
    def test_marks_failed_with_error(self, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="fail-dev-1", user_id=admin_user.id)
        )
        created = db_sync_session_handler.create_session(device.id, admin_user.id)

        result = db_sync_session_handler.fail_session(
            created.id, error_message="Connection lost"
        )
        assert result.status == SyncSessionStatus.FAILED
        assert result.error_message == "Connection lost"
        assert result.completed_at is not None

    def test_marks_failed_without_error(self, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="fail-dev-2", user_id=admin_user.id)
        )
        created = db_sync_session_handler.create_session(device.id, admin_user.id)

        result = db_sync_session_handler.fail_session(created.id)
        assert result.status == SyncSessionStatus.FAILED
        assert result.error_message is None


class TestIncrementOperationsCompleted:
    def test_increments_counter(self, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="inc-dev-1", user_id=admin_user.id)
        )
        session = db_sync_session_handler.create_session(device.id, admin_user.id)
        assert session.operations_completed == 0

        db_sync_session_handler.increment_operations_completed(
            session.id, admin_user.id
        )
        db_sync_session_handler.increment_operations_completed(
            session.id, admin_user.id
        )
        db_sync_session_handler.increment_operations_completed(
            session.id, admin_user.id
        )

        result = db_sync_session_handler.get_session(session.id, admin_user.id)
        assert result is not None
        assert result.operations_completed == 3

    def test_noop_on_nonexistent_session(self, admin_user: User):
        db_sync_session_handler.increment_operations_completed(999999, admin_user.id)


class TestNoResultFoundOnMissingSession:
    def test_update_session_raises(self, admin_user: User):
        with pytest.raises(NoResultFound):
            db_sync_session_handler.update_session(
                999999, {"status": SyncSessionStatus.IN_PROGRESS}
            )

    def test_complete_session_raises(self, admin_user: User):
        with pytest.raises(NoResultFound):
            db_sync_session_handler.complete_session(999999)

    def test_fail_session_raises(self, admin_user: User):
        with pytest.raises(NoResultFound):
            db_sync_session_handler.fail_session(999999, error_message="test")


class TestCancelActiveSessions:
    def test_cancels_active_sessions(self, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="cancel-dev-1", user_id=admin_user.id)
        )
        db_sync_session_handler.create_session(device.id, admin_user.id)
        s2 = db_sync_session_handler.create_session(device.id, admin_user.id)
        db_sync_session_handler.update_session(
            s2.id, {"status": SyncSessionStatus.IN_PROGRESS}
        )

        count = db_sync_session_handler.cancel_active_sessions(device.id, admin_user.id)
        assert count == 2

        active = db_sync_session_handler.get_active_session(device.id, admin_user.id)
        assert active is None

    def test_does_not_cancel_completed(self, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="cancel-dev-2", user_id=admin_user.id)
        )
        created = db_sync_session_handler.create_session(device.id, admin_user.id)
        db_sync_session_handler.complete_session(created.id)

        count = db_sync_session_handler.cancel_active_sessions(device.id, admin_user.id)
        assert count == 0


class TestGetSessions:
    def test_list_sessions_for_user(self, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="list-dev-1", user_id=admin_user.id)
        )
        for _ in range(3):
            db_sync_session_handler.create_session(device.id, admin_user.id)

        sessions = db_sync_session_handler.get_sessions(admin_user.id)
        assert len(sessions) == 3

    def test_filter_by_device(self, admin_user: User):
        d1 = db_device_handler.add_device(
            Device(id="list-dev-2a", user_id=admin_user.id)
        )
        d2 = db_device_handler.add_device(
            Device(id="list-dev-2b", user_id=admin_user.id)
        )
        db_sync_session_handler.create_session(d1.id, admin_user.id)
        db_sync_session_handler.create_session(d2.id, admin_user.id)
        db_sync_session_handler.create_session(d2.id, admin_user.id)

        sessions = db_sync_session_handler.get_sessions(admin_user.id, device_id=d2.id)
        assert len(sessions) == 2
        assert all(s.device_id == d2.id for s in sessions)

    def test_filter_by_status(self, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="list-dev-3", user_id=admin_user.id)
        )
        s1 = db_sync_session_handler.create_session(device.id, admin_user.id)
        db_sync_session_handler.create_session(device.id, admin_user.id)
        db_sync_session_handler.complete_session(s1.id)

        sessions = db_sync_session_handler.get_sessions(
            admin_user.id, status=SyncSessionStatus.COMPLETED
        )
        assert len(sessions) == 1
        assert sessions[0].status == SyncSessionStatus.COMPLETED

    def test_respects_limit(self, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="list-dev-4", user_id=admin_user.id)
        )
        for _ in range(5):
            db_sync_session_handler.create_session(device.id, admin_user.id)

        sessions = db_sync_session_handler.get_sessions(admin_user.id, limit=2)
        assert len(sessions) == 2

    def test_user_isolation(self, admin_user: User, editor_user: User):
        d1 = db_device_handler.add_device(Device(id="iso-dev-1", user_id=admin_user.id))
        d2 = db_device_handler.add_device(
            Device(id="iso-dev-2", user_id=editor_user.id)
        )
        db_sync_session_handler.create_session(d1.id, admin_user.id)
        db_sync_session_handler.create_session(d2.id, editor_user.id)

        admin_sessions = db_sync_session_handler.get_sessions(admin_user.id)
        assert len(admin_sessions) == 1
        assert admin_sessions[0].user_id == admin_user.id

        editor_sessions = db_sync_session_handler.get_sessions(editor_user.id)
        assert len(editor_sessions) == 1
        assert editor_sessions[0].user_id == editor_user.id
