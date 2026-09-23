from collections.abc import Sequence
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from handler import notification_handler
from handler.notification_handler import (
    NOTIFICATIONS_NEW_EVENT,
    notify,
    notify_admins,
    notify_user_or_admins,
    recipient_ids,
)
from models.notification import Notification, NotificationKind, NotificationLevel


def _stored(notifications: Sequence[Notification]) -> Sequence[Notification]:
    for i, notification in enumerate(notifications, start=7):
        notification.id = i
        notification.created_at = datetime(2026, 9, 23, tzinfo=timezone.utc)
        notification.read_at = None
        notification.actor = None
    return notifications


@pytest.fixture
def emit(mocker):
    return mocker.patch.object(
        notification_handler.socket_handler, "emit_to_user", AsyncMock()
    )


@pytest.fixture
def add_notifications(mocker):
    return mocker.patch.object(
        notification_handler.db_notification_handler,
        "add_notifications",
        side_effect=_stored,
    )


class TestNotify:
    async def test_stores_then_pushes_the_stored_row(self, emit, add_notifications):
        await notify(
            3,
            NotificationKind.SCAN_COMPLETED,
            NotificationLevel.SUCCESS,
            {"new_roms": 2},
        )

        [stored] = add_notifications.call_args.args[0]
        assert stored.user_id == 3
        assert stored.kind == NotificationKind.SCAN_COMPLETED
        user_id, event, payload = emit.await_args.args
        assert (user_id, event) == (3, NOTIFICATIONS_NEW_EVENT)
        assert payload["id"] == 7
        assert payload["data"] == {"new_roms": 2}
        assert payload["created_at"].startswith("2026-09-23")

    async def test_carries_its_own_content_for_a_custom_kind(
        self, emit, add_notifications
    ):
        await notify(
            3,
            "argosy.sync_done",
            NotificationLevel.INFO,
            title="Sync finished",
            body="12 saves uploaded",
            link="/rom/12",
            icon="mdi-sync",
        )

        payload = emit.await_args.args[2]
        assert payload["kind"] == "argosy.sync_done"
        assert (payload["title"], payload["body"]) == (
            "Sync finished",
            "12 saves uploaded",
        )
        assert (payload["link"], payload["icon"]) == ("/rom/12", "mdi-sync")

    async def test_a_storage_failure_pushes_nothing(self, mocker, emit):
        mocker.patch.object(
            notification_handler.db_notification_handler,
            "add_notifications",
            side_effect=RuntimeError("database gone"),
        )

        await notify(3, NotificationKind.TASK_FAILED, NotificationLevel.ERROR)

        emit.assert_not_awaited()


class TestNotifyAdmins:
    async def test_stores_one_row_per_admin_in_one_go(
        self, mocker, emit, add_notifications
    ):
        mocker.patch.object(notification_handler, "recipient_ids", return_value=[1, 4])

        await notify_admins(NotificationKind.TASK_FAILED, NotificationLevel.ERROR)

        add_notifications.assert_called_once()
        assert [n.user_id for n in add_notifications.call_args.args[0]] == [1, 4]
        assert emit.await_count == 2


class TestRecipientIds:
    @pytest.fixture
    def users(self, mocker):
        return mocker.patch.object(
            notification_handler.db_user_handler,
            "get_users",
            return_value=[
                MagicMock(id=1, enabled=True),
                MagicMock(id=2, enabled=False),
                MagicMock(id=3, enabled=True),
            ],
        )

    def test_everyone_enabled(self, users):
        assert recipient_ids("all") == [1, 3]

    def test_only_the_named_enabled_users(self, users):
        assert recipient_ids([3, 2, 3, 99]) == [3]


class TestNotifyUserOrAdmins:
    @pytest.fixture
    def targets(self, mocker):
        return (
            mocker.patch.object(notification_handler, "notify", AsyncMock()),
            mocker.patch.object(notification_handler, "notify_admins", AsyncMock()),
        )

    async def test_the_starter_hears_first(self, targets):
        notify_mock, admins_mock = targets

        await notify_user_or_admins(
            5,
            NotificationKind.TASK_FAILED,
            NotificationLevel.ERROR,
            {},
            admins_too=True,
        )

        notify_mock.assert_awaited_once()
        admins_mock.assert_not_awaited()

    @pytest.mark.parametrize("admins_too", [True, False])
    async def test_nobody_started_it(self, targets, admins_too):
        notify_mock, admins_mock = targets

        await notify_user_or_admins(
            None,
            NotificationKind.TASK_FAILED,
            NotificationLevel.ERROR,
            {},
            admins_too=admins_too,
        )

        notify_mock.assert_not_awaited()
        assert admins_mock.await_count == int(admins_too)
