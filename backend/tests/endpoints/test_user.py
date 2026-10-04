from datetime import timedelta

from fastapi import status

from exceptions.database_exceptions import LastAdminError
from handler.auth.base_handler import oauth_handler
from handler.auth.middleware.redis_session_middleware import RedisSessionMiddleware
from handler.database import db_permission_handler, db_user_handler
from models.permission import PermAction, PermEntity
from models.user import Role, User


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_an_unknown_user_is_not_found(client, access_token: str):
    response = client.put(
        "/api/users/999999", data={"ra_username": "x"}, headers=_bearer(access_token)
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_non_admin_cannot_edit_another_user(
    client, viewer_access_token: str, admin_user: User
):
    response = client.put(
        f"/api/users/{admin_user.id}",
        data={"password": "hijacked_password"},
        headers=_bearer(viewer_access_token),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    unchanged = db_user_handler.get_user(admin_user.id)
    assert unchanged and unchanged.hashed_password == admin_user.hashed_password


def test_non_admin_can_edit_themselves(
    client, viewer_access_token: str, viewer_user: User
):
    response = client.put(
        f"/api/users/{viewer_user.id}",
        data={"email": "Viewer@Example.com"},
        headers=_bearer(viewer_access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["email"] == "viewer@example.com"


def test_non_admin_cannot_promote_or_disable_themselves(
    client, viewer_access_token: str, viewer_user: User
):
    client.put(
        f"/api/users/{viewer_user.id}",
        data={"role": "admin", "enabled": "false"},
        headers=_bearer(viewer_access_token),
    )

    updated = db_user_handler.get_user(viewer_user.id)
    assert updated and (updated.role, updated.enabled) == (Role.USER, True)


def test_admin_cannot_demote_or_disable_themselves(
    client, access_token: str, admin_user: User
):
    client.put(
        f"/api/users/{admin_user.id}",
        data={"role": "user", "enabled": "false"},
        headers=_bearer(access_token),
    )

    updated = db_user_handler.get_user(admin_user.id)
    assert updated and (updated.role, updated.enabled) == (Role.ADMIN, True)


def test_admin_can_demote_another_admin(client, access_token: str, admin_user: User):
    other = db_user_handler.add_user(
        User(username="other_admin", hashed_password="x", role=Role.ADMIN)
    )

    response = client.put(
        f"/api/users/{other.id}", data={"role": "user"}, headers=_bearer(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["role"] == Role.USER


def test_rename_is_lowercased(client, access_token: str, viewer_user: User):
    response = client.put(
        f"/api/users/{viewer_user.id}",
        data={"username": "Renamed_Viewer"},
        headers=_bearer(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["username"] == "renamed_viewer"


def test_rename_to_a_taken_username_is_rejected(
    client, access_token: str, viewer_user: User, admin_user: User
):
    response = client.put(
        f"/api/users/{viewer_user.id}",
        data={"username": admin_user.username},
        headers=_bearer(access_token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    unchanged = db_user_handler.get_user(viewer_user.id)
    assert unchanged and unchanged.username == "test_viewer"


def test_rename_to_an_invalid_username_is_rejected(
    client, access_token: str, viewer_user: User
):
    response = client.put(
        f"/api/users/{viewer_user.id}",
        data={"username": "ab"},
        headers=_bearer(access_token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_update_to_a_taken_email_is_rejected(
    client, access_token: str, viewer_user: User, editor_user: User
):
    db_user_handler.update_user(editor_user.id, {"email": "taken@example.com"})

    response = client.put(
        f"/api/users/{viewer_user.id}",
        data={"email": "taken@example.com"},
        headers=_bearer(access_token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_update_with_an_empty_email_clears_it(
    client, access_token: str, viewer_user: User
):
    db_user_handler.update_user(viewer_user.id, {"email": "viewer@example.com"})

    response = client.put(
        f"/api/users/{viewer_user.id}",
        data={"email": ""},
        headers=_bearer(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["email"] is None


def test_update_to_a_short_password_is_rejected(
    client, access_token: str, viewer_user: User
):
    response = client.put(
        f"/api/users/{viewer_user.id}",
        data={"password": "short"},
        headers=_bearer(access_token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_a_delegated_user_manager_cannot_delete_the_last_admin(
    client, admin_user: User, viewer_user: User
):
    db_permission_handler.replace_user_overrides(
        viewer_user.id, [(PermEntity.USERS, PermAction.WRITE, True, False)]
    )
    manager = db_user_handler.get_user(viewer_user.id)
    assert manager
    token = oauth_handler.create_access_token(
        data={
            "sub": manager.username,
            "iss": "romm:oauth",
            "scopes": " ".join(manager.oauth_scopes),
        },
        expires_delta=timedelta(minutes=5),
    )

    response = client.delete(f"/api/users/{admin_user.id}", headers=_bearer(token))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "You cannot delete the last admin user"
    assert db_user_handler.get_user(admin_user.id) is not None


def test_a_demotion_that_would_leave_no_admin_is_refused(
    client, access_token: str, admin_user: User, mocker
):
    other = db_user_handler.add_user(
        User(username="other_admin", hashed_password="x", role=Role.ADMIN)
    )
    # Only reachable when another request demotes this admin at the same time.
    mocker.patch.object(
        db_user_handler,
        "refuse_removing_the_last_admin",
        side_effect=LastAdminError(other.id),
    )

    response = client.put(
        f"/api/users/{other.id}", data={"role": "user"}, headers=_bearer(access_token)
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "You cannot demote the last admin user"
    unchanged = db_user_handler.get_user(other.id)
    assert unchanged and unchanged.role == Role.ADMIN


def test_a_refused_demotion_does_not_log_the_admin_out(
    client, access_token: str, admin_user: User, mocker
):
    other = db_user_handler.add_user(
        User(username="other_admin", hashed_password="x", role=Role.ADMIN)
    )
    mocker.patch.object(
        db_user_handler,
        "refuse_removing_the_last_admin",
        side_effect=LastAdminError(other.id),
    )
    clear_sessions = mocker.patch.object(
        RedisSessionMiddleware, "clear_user_sessions", mocker.AsyncMock()
    )

    response = client.put(
        f"/api/users/{other.id}",
        data={"role": "user", "password": "a_new_password"},
        headers=_bearer(access_token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    clear_sessions.assert_not_awaited()
    unchanged = db_user_handler.get_user(other.id)
    assert unchanged and unchanged.hashed_password == "x"
