from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from handler import notification_handler
from handler.notification_handler import (
    NOTIFICATIONS_NEW_EVENT,
    emit_to_user,
    notify,
    notify_admins,
)
from models.notification import Notification, NotificationKind, NotificationLevel


def _stored(notification: Notification) -> Notification:
    notification.id = 7
    notification.created_at = datetime(2026, 9, 23, tzinfo=timezone.utc)
    notification.read_at = None
    notification.actor = None
    return notification


@pytest.fixture
def emit(mocker):
    return mocker.patch.object(notification_handler, "emit_to_user", AsyncMock())


@pytest.fixture
def add_notification(mocker):
    return mocker.patch.object(
        notification_handler.db_notification_handler,
        "add_notification",
        side_effect=_stored,
    )


class TestNotify:
    async def test_stores_then_pushes_the_stored_row(self, emit, add_notification):
        await notify(
            3,
            NotificationKind.SCAN_COMPLETED,
            NotificationLevel.SUCCESS,
            {"new_roms": 2},
        )

        stored = add_notification.call_args.args[0]
        assert stored.user_id == 3
        assert stored.kind == NotificationKind.SCAN_COMPLETED
        user_id, event, payload = emit.await_args.args
        assert (user_id, event) == (3, NOTIFICATIONS_NEW_EVENT)
        assert payload["id"] == 7
        assert payload["data"] == {"new_roms": 2}
        assert payload["created_at"].startswith("2026-09-23")

    async def test_a_storage_failure_pushes_nothing(self, mocker, emit):
        mocker.patch.object(
            notification_handler.db_notification_handler,
            "add_notification",
            side_effect=RuntimeError("database gone"),
        )

        await notify(3, NotificationKind.TASK_FAILED, NotificationLevel.ERROR)

        emit.assert_not_awaited()


class TestNotifyAdmins:
    async def test_skips_disabled_admins(self, mocker):
        enabled = MagicMock(id=1, enabled=True)
        disabled = MagicMock(id=2, enabled=False)
        mocker.patch.object(
            notification_handler.db_user_handler,
            "get_admin_users",
            return_value=[enabled, disabled],
        )
        notify_mock = mocker.patch.object(notification_handler, "notify", AsyncMock())

        await notify_admins(NotificationKind.TASK_FAILED, NotificationLevel.ERROR)

        notify_mock.assert_awaited_once_with(
            1, NotificationKind.TASK_FAILED, NotificationLevel.ERROR, None
        )


class TestEmitToUser:
    async def test_targets_the_users_room(self, mocker):
        manager = MagicMock(emit=AsyncMock())
        mocker.patch.object(
            notification_handler.socketio, "AsyncRedisManager", return_value=manager
        )

        await emit_to_user(5, "notifications:read", {"ids": None})

        manager.emit.assert_awaited_once_with(
            "notifications:read", {"ids": None}, room="user:5"
        )

    async def test_swallows_a_broker_failure(self, mocker):
        manager = MagicMock(emit=AsyncMock(side_effect=ConnectionError("redis")))
        mocker.patch.object(
            notification_handler.socketio, "AsyncRedisManager", return_value=manager
        )

        await emit_to_user(5, "notifications:read", {"ids": None})
