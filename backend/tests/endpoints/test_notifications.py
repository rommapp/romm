from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import status

from handler.auth import oauth_handler
from handler.database import db_notification_handler
from handler.socket_handler import socket_handler
from models.notification import (
    MAX_NOTIFICATIONS_PER_USER,
    Notification,
    NotificationKind,
    NotificationLevel,
)
from models.user import User


def _add(user: User, minutes_ago: int = 0, **overrides) -> Notification:
    [stored] = db_notification_handler.add_notifications(
        [
            Notification(
                user_id=user.id,
                kind=NotificationKind.TASK_COMPLETED,
                level=NotificationLevel.SUCCESS,
                data={"task": "cleanup_missing_roms"},
                created_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
                **overrides,
            )
        ]
    )
    return stored


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def emit(mocker):
    return mocker.patch.object(socket_handler, "emit_to_user", AsyncMock())


class TestListNotifications:
    def test_lists_only_the_callers_newest_first(
        self, client, access_token, admin_user, viewer_user
    ):
        older = _add(admin_user, minutes_ago=5)
        newer = _add(admin_user, minutes_ago=1, actor_id=viewer_user.id)
        _add(viewer_user)

        response = client.get("/api/notifications", headers=_auth(access_token))

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert [n["id"] for n in body] == [newer.id, older.id]
        assert body[0]["actor"]["username"] == viewer_user.username
        assert body[0]["kind"] == "task_completed"
        assert body[0]["read_at"] is None
        assert body[1]["actor"] is None


class TestMarkRead:
    def test_marks_the_given_ids(self, client, access_token, admin_user, emit):
        first = _add(admin_user)
        second = _add(admin_user)

        response = client.post(
            "/api/notifications/read",
            json={"ids": [first.id]},
            headers=_auth(access_token),
        )

        assert response.status_code == status.HTTP_200_OK
        read = {
            n.id: n.read_at
            for n in db_notification_handler.get_notifications(admin_user.id)
        }
        assert read[first.id] is not None
        assert read[second.id] is None
        emit.assert_awaited_once_with(
            admin_user.id, "notifications:read", {"ids": [first.id]}
        )

    def test_null_marks_everything(self, client, access_token, admin_user, emit):
        _add(admin_user)
        _add(admin_user)

        client.post(
            "/api/notifications/read", json={"ids": None}, headers=_auth(access_token)
        )

        assert all(
            n.read_at for n in db_notification_handler.get_notifications(admin_user.id)
        )

    def test_leaves_other_users_alone(
        self, client, access_token, admin_user, viewer_user, emit
    ):
        theirs = _add(viewer_user)

        client.post(
            "/api/notifications/read",
            json={"ids": [theirs.id]},
            headers=_auth(access_token),
        )

        [unchanged] = db_notification_handler.get_notifications(viewer_user.id)
        assert unchanged.read_at is None


class TestDismiss:
    def test_dismisses_one_for_good(self, client, access_token, admin_user, emit):
        gone = _add(admin_user)
        kept = _add(admin_user)

        response = client.delete(
            f"/api/notifications/{gone.id}", headers=_auth(access_token)
        )

        assert response.status_code == status.HTTP_200_OK
        remaining = db_notification_handler.get_notifications(admin_user.id)
        assert [n.id for n in remaining] == [kept.id]
        emit.assert_awaited_once_with(
            admin_user.id, "notifications:dismissed", {"ids": [gone.id]}
        )

    def test_someone_elses_is_not_found(self, client, access_token, viewer_user, emit):
        theirs = _add(viewer_user)

        response = client.delete(
            f"/api/notifications/{theirs.id}", headers=_auth(access_token)
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert len(db_notification_handler.get_notifications(viewer_user.id)) == 1
        emit.assert_not_awaited()

    def test_dismisses_all_of_the_callers(
        self, client, access_token, admin_user, viewer_user, emit
    ):
        _add(admin_user)
        _add(admin_user)
        _add(viewer_user)

        response = client.delete("/api/notifications", headers=_auth(access_token))

        assert response.status_code == status.HTTP_200_OK
        assert db_notification_handler.get_notifications(admin_user.id) == []
        assert len(db_notification_handler.get_notifications(viewer_user.id)) == 1
        emit.assert_awaited_once_with(
            admin_user.id, "notifications:dismissed", {"ids": None}
        )


def test_an_inbox_keeps_only_the_newest(admin_user):
    oldest = _add(admin_user, minutes_ago=MAX_NOTIFICATIONS_PER_USER + 1)
    for minutes_ago in range(MAX_NOTIFICATIONS_PER_USER, 0, -1):
        _add(admin_user, minutes_ago=minutes_ago)

    remaining = db_notification_handler.get_notifications(admin_user.id)

    assert len(remaining) == MAX_NOTIFICATIONS_PER_USER
    assert oldest.id not in {n.id for n in remaining}


class TestCreateNotification:
    def test_a_user_notifies_themselves(
        self, client, viewer_access_token, viewer_user, emit
    ):
        response = client.post(
            "/api/notifications",
            json={
                "title": "Sync finished",
                "body": "12 saves uploaded",
                "kind": "argosy.sync_done",
                "level": "success",
                "link": "/rom/12",
                "icon": "mdi-sync",
                "data": {"device": "deck"},
            },
            headers=_auth(viewer_access_token),
        )

        assert response.status_code == status.HTTP_201_CREATED
        [sent] = response.json()
        assert sent["title"] == "Sync finished"
        assert sent["kind"] == "argosy.sync_done"
        assert sent["actor"] is None
        [stored] = db_notification_handler.get_notifications(viewer_user.id)
        assert (stored.link, stored.data) == ("/rom/12", {"device": "deck"})
        emit.assert_awaited_once()

    def test_only_an_admin_notifies_others(
        self, client, viewer_access_token, admin_user, emit
    ):
        response = client.post(
            "/api/notifications",
            json={"title": "Hello", "recipients": [admin_user.id]},
            headers=_auth(viewer_access_token),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert db_notification_handler.get_notifications(admin_user.id) == []

    def test_an_admin_notifies_everyone_as_the_sender(
        self, client, access_token, admin_user, viewer_user, editor_user, emit
    ):
        response = client.post(
            "/api/notifications",
            json={
                "title": "Maintenance tonight",
                "level": "warning",
                "recipients": "all",
            },
            headers=_auth(access_token),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.json()) == 3
        [to_viewer] = db_notification_handler.get_notifications(viewer_user.id)
        assert to_viewer.actor_id == admin_user.id
        [to_self] = db_notification_handler.get_notifications(admin_user.id)
        assert to_self.actor_id is None

    def test_an_admin_notifies_only_the_admins(
        self, client, access_token, admin_user, viewer_user, emit
    ):
        client.post(
            "/api/notifications",
            json={"title": "Disk almost full", "recipients": "admins"},
            headers=_auth(access_token),
        )

        assert len(db_notification_handler.get_notifications(admin_user.id)) == 1
        assert db_notification_handler.get_notifications(viewer_user.id) == []

    def test_an_unknown_recipient_is_not_found(
        self, client, access_token, viewer_user, emit
    ):
        response = client.post(
            "/api/notifications",
            json={"title": "Hello", "recipients": [viewer_user.id, 999_999]},
            headers=_auth(access_token),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert db_notification_handler.get_notifications(viewer_user.id) == []

    @pytest.mark.parametrize(
        "field",
        [
            {"kind": "role_changed"},
            {"link": "https://example.com"},
            {"link": "//example.com/login"},
            {"link": "/\\example.com"},
            {"icon": "not-an-icon"},
            {"title": ""},
            {"data": {"blob": "x" * 5000}},
            {"title": "nul\u0000byte"},
            {"recipients": []},
        ],
    )
    def test_rejects_what_a_client_may_not_send(
        self, client, access_token, admin_user, field, emit
    ):
        response = client.post(
            "/api/notifications",
            json={"title": "Hello", **field},
            headers=_auth(access_token),
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert db_notification_handler.get_notifications(admin_user.id) == []


def test_an_admin_token_without_users_write_notifies_only_itself(
    client, admin_user, viewer_user, emit
):
    token = oauth_handler.create_access_token(
        data={
            "sub": admin_user.username,
            "iss": "romm:oauth",
            "scopes": "me.read me.write",
        },
        expires_delta=timedelta(minutes=5),
    )

    response = client.post(
        "/api/notifications",
        json={"title": "Hello", "recipients": "all"},
        headers=_auth(token),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert db_notification_handler.get_notifications(viewer_user.id) == []
