import base64
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import status

from endpoints.user import STEAM_ACHIEVEMENTS_DISABLED, STEAM_GAME_DETAILS_PRIVATE
from exceptions.database_exceptions import LastAdminError
from handler.auth.base_handler import auth_handler, oauth_handler
from handler.auth.middleware.redis_session_middleware import RedisSessionMiddleware
from handler.database import db_permission_handler, db_user_handler
from handler.metadata.steam_handler import SteamHandler
from models.permission import PermAction, PermEntity
from models.user import Role, User
from tasks.scheduled.sync_steam_achievements_progress import (
    SteamGameDetailsPrivateError,
)


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
        data={
            "email": "Viewer@Example.com",
            "current_password": "test_viewer_password",
        },
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


def _delegated_user_manager_token(user: User) -> str:
    db_permission_handler.replace_user_overrides(
        user.id, [(PermEntity.USERS, PermAction.WRITE, True, False)]
    )
    manager = db_user_handler.get_user(user.id)
    assert manager
    return oauth_handler.create_access_token(
        data={
            "sub": manager.username,
            "iss": "romm:oauth",
            "scopes": " ".join(manager.oauth_scopes),
        },
        expires_delta=timedelta(minutes=5),
    )


def test_a_delegated_user_manager_cannot_delete_an_admin(
    client, admin_user: User, viewer_user: User
):
    other = db_user_handler.add_user(
        User(username="other_admin", hashed_password="x", role=Role.ADMIN)
    )
    token = _delegated_user_manager_token(viewer_user)

    for target in (admin_user, other):
        response = client.delete(f"/api/users/{target.id}", headers=_bearer(token))

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert db_user_handler.get_user(target.id) is not None


def test_a_delegated_user_manager_can_delete_a_non_admin(
    client, admin_user: User, viewer_user: User, editor_user: User
):
    token = _delegated_user_manager_token(viewer_user)

    response = client.delete(f"/api/users/{editor_user.id}", headers=_bearer(token))

    assert response.status_code == status.HTTP_200_OK
    assert db_user_handler.get_user(editor_user.id) is None


def test_a_delegated_user_manager_can_edit_a_non_admin(
    client, admin_user: User, viewer_user: User, editor_user: User
):
    token = _delegated_user_manager_token(viewer_user)

    response = client.put(
        f"/api/users/{editor_user.id}",
        data={"email": "editor@example.com"},
        headers=_bearer(token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["email"] == "editor@example.com"


def test_a_delegated_user_manager_cannot_edit_an_admin(
    client, admin_user: User, viewer_user: User
):
    token = _delegated_user_manager_token(viewer_user)

    response = client.put(
        f"/api/users/{admin_user.id}",
        data={"password": "hijacked_password"},
        headers=_bearer(token),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    unchanged = db_user_handler.get_user(admin_user.id)
    assert unchanged and unchanged.hashed_password == admin_user.hashed_password


def test_a_delegated_user_manager_cannot_promote_to_admin(
    client, admin_user: User, viewer_user: User, editor_user: User
):
    token = _delegated_user_manager_token(viewer_user)

    response = client.put(
        f"/api/users/{editor_user.id}", data={"role": "admin"}, headers=_bearer(token)
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    unchanged = db_user_handler.get_user(editor_user.id)
    assert unchanged and unchanged.role == editor_user.role


def test_deleting_the_last_admin_is_refused(
    client, access_token: str, admin_user: User, mocker
):
    other = db_user_handler.add_user(
        User(username="other_admin", hashed_password="x", role=Role.ADMIN)
    )
    # Only reachable when another request removes this admin at the same time.
    mocker.patch.object(
        db_user_handler,
        "refuse_removing_the_last_admin",
        side_effect=LastAdminError(other.id),
    )

    response = client.delete(f"/api/users/{other.id}", headers=_bearer(access_token))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "You cannot delete the last admin user"
    assert db_user_handler.get_user(other.id) is not None


def test_an_admin_token_without_users_write_cannot_edit_another_user(
    client, admin_user: User, viewer_user: User
):
    token = oauth_handler.create_access_token(
        data={"sub": admin_user.username, "iss": "romm:oauth", "scopes": "me.write"},
        expires_delta=timedelta(minutes=5),
    )

    response = client.put(
        f"/api/users/{viewer_user.id}",
        data={"password": "hijacked_password"},
        headers=_bearer(token),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    unchanged = db_user_handler.get_user(viewer_user.id)
    assert unchanged and unchanged.hashed_password == viewer_user.hashed_password


def test_an_admin_token_without_users_write_cannot_refresh_another_users_ra(
    client, admin_user: User, viewer_user: User
):
    token = oauth_handler.create_access_token(
        data={"sub": admin_user.username, "iss": "romm:oauth", "scopes": "me.write"},
        expires_delta=timedelta(minutes=5),
    )

    response = client.post(
        f"/api/users/{viewer_user.id}/ra/refresh", headers=_bearer(token)
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


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


def _password_matches(user_id: int, password: str) -> bool:
    user = db_user_handler.get_user(user_id)
    assert user
    return auth_handler.verify_password(password, user.hashed_password)


def test_own_password_change_with_the_current_password(
    client, viewer_access_token: str, viewer_user: User
):
    response = client.put(
        f"/api/users/{viewer_user.id}",
        data={
            "password": "a_new_password",
            "current_password": "test_viewer_password",
        },
        headers=_bearer(viewer_access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert _password_matches(viewer_user.id, "a_new_password")


def test_own_password_change_with_a_wrong_current_password_is_refused(
    client, viewer_access_token: str, viewer_user: User
):
    response = client.put(
        f"/api/users/{viewer_user.id}",
        data={"password": "a_new_password", "current_password": "not_my_password"},
        headers=_bearer(viewer_access_token),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Current password is incorrect"
    assert _password_matches(viewer_user.id, "test_viewer_password")


def test_own_password_change_without_the_current_password_is_refused(
    client, viewer_access_token: str, viewer_user: User
):
    response = client.put(
        f"/api/users/{viewer_user.id}",
        data={"password": "a_new_password"},
        headers=_bearer(viewer_access_token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert _password_matches(viewer_user.id, "test_viewer_password")


def test_admin_changes_their_own_password_only_with_the_current_one(
    client, access_token: str, admin_user: User
):
    response = client.put(
        f"/api/users/{admin_user.id}",
        data={"password": "a_new_password"},
        headers=_bearer(access_token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert _password_matches(admin_user.id, "test_admin_password")


def test_admin_resets_another_users_password_without_theirs(
    client, access_token: str, viewer_user: User
):
    response = client.put(
        f"/api/users/{viewer_user.id}",
        data={"password": "reset_by_admin"},
        headers=_bearer(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert _password_matches(viewer_user.id, "reset_by_admin")


def test_own_email_change_without_the_current_password_is_refused(
    client, viewer_access_token: str, viewer_user: User
):
    response = client.put(
        f"/api/users/{viewer_user.id}",
        data={"email": "attacker@example.com"},
        headers=_bearer(viewer_access_token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    unchanged = db_user_handler.get_user(viewer_user.id)
    assert unchanged and unchanged.email is None


def test_resending_the_unchanged_email_needs_no_current_password(
    client, viewer_access_token: str, viewer_user: User
):
    db_user_handler.update_user(viewer_user.id, {"email": "viewer@example.com"})

    response = client.put(
        f"/api/users/{viewer_user.id}",
        data={"email": "viewer@example.com", "ra_username": "retro_viewer"},
        headers=_bearer(viewer_access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["ra_username"] == "retro_viewer"


def test_own_username_change_needs_the_current_password(
    client, viewer_access_token: str, viewer_user: User
):
    refused = client.put(
        f"/api/users/{viewer_user.id}",
        data={"username": "renamed_viewer"},
        headers=_bearer(viewer_access_token),
    )
    assert refused.status_code == status.HTTP_400_BAD_REQUEST
    unchanged = db_user_handler.get_user(viewer_user.id)
    assert unchanged and unchanged.username == viewer_user.username

    response = client.put(
        f"/api/users/{viewer_user.id}",
        data={
            "username": "renamed_viewer",
            "current_password": "test_viewer_password",
        },
        headers=_bearer(viewer_access_token),
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["username"] == "renamed_viewer"


def test_a_case_only_username_edit_is_no_change(
    client, viewer_access_token: str, viewer_user: User
):
    response = client.put(
        f"/api/users/{viewer_user.id}",
        data={"username": viewer_user.username.upper()},
        headers=_bearer(viewer_access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["username"] == viewer_user.username


def test_admin_renames_another_user_without_their_password(
    client, access_token: str, viewer_user: User
):
    response = client.put(
        f"/api/users/{viewer_user.id}",
        data={"username": "renamed_by_admin"},
        headers=_bearer(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["username"] == "renamed_by_admin"


def test_a_case_only_email_edit_is_no_change(
    client, viewer_access_token: str, viewer_user: User
):
    db_user_handler.update_user(viewer_user.id, {"email": "Viewer@Example.com"})

    response = client.put(
        f"/api/users/{viewer_user.id}",
        data={"email": "viewer@example.com"},
        headers=_bearer(viewer_access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["email"] == "Viewer@Example.com"


def test_an_oidc_linked_account_cannot_change_its_own_email(
    client, viewer_access_token: str, viewer_user: User, mocker
):
    mocker.patch("models.user.OIDC_ENABLED", True)
    db_user_handler.update_user(
        viewer_user.id, {"oidc_issuer": "https://idp", "oidc_sub": "viewer-sub"}
    )

    response = client.put(
        f"/api/users/{viewer_user.id}",
        data={
            "email": "new@example.com",
            "current_password": "test_viewer_password",
        },
        headers=_bearer(viewer_access_token),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert (
        response.json()["detail"] == "Your email is managed by your identity provider"
    )
    unchanged = db_user_handler.get_user(viewer_user.id)
    assert unchanged and unchanged.email is None


def test_admin_changes_an_oidc_linked_users_email(
    client, access_token: str, viewer_user: User, mocker
):
    mocker.patch("models.user.OIDC_ENABLED", True)
    db_user_handler.update_user(
        viewer_user.id, {"oidc_issuer": "https://idp", "oidc_sub": "viewer-sub"}
    )

    response = client.put(
        f"/api/users/{viewer_user.id}",
        data={"email": "fixed@example.com"},
        headers=_bearer(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["email"] == "fixed@example.com"


def test_a_password_less_account_cannot_set_a_password_with_a_token(
    client, viewer_access_token: str, viewer_user: User
):
    db_user_handler.update_user(viewer_user.id, {"hashed_password": "placeholder"})

    response = client.put(
        f"/api/users/{viewer_user.id}",
        data={"password": "a_first_password"},
        headers=_bearer(viewer_access_token),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert not _password_matches(viewer_user.id, "a_first_password")


async def test_a_password_less_account_sets_a_first_password_from_its_session(
    client, viewer_user: User
):
    basic_auth = base64.b64encode(b"test_viewer:test_viewer_password").decode()
    login = client.post("/api/login", headers={"Authorization": f"Basic {basic_auth}"})
    assert login.status_code == status.HTTP_200_OK
    session = {"Cookie": f"romm_session={login.cookies['romm_session']}"}
    # What an OIDC-provisioned account holds instead of a bcrypt hash.
    db_user_handler.update_user(viewer_user.id, {"hashed_password": "placeholder"})

    me = client.get("/api/users/me", headers=session)
    assert me.json()["has_password"] is False

    response = client.put(
        f"/api/users/{viewer_user.id}",
        data={"password": "a_first_password"},
        headers=session,
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["has_password"] is True
    assert _password_matches(viewer_user.id, "a_first_password")
    await RedisSessionMiddleware.clear_user_sessions(viewer_user.username)


STEAM_ID = "76561197960287930"


@pytest.fixture
def steam_achievements(mocker) -> SimpleNamespace:
    """Steam achievements enabled, with every profile public and resolvable."""
    mocker.patch.object(SteamHandler, "achievements_enabled", return_value=True)
    return SimpleNamespace(
        resolve_profile=mocker.patch.object(
            SteamHandler, "resolve_profile", AsyncMock(return_value=STEAM_ID)
        ),
        can_read_games=mocker.patch.object(
            SteamHandler, "can_read_games", AsyncMock(return_value=True)
        ),
    )


def _link_steam(client, token: str, user: User, value: str):
    return client.put(
        f"/api/users/{user.id}", data={"steam_id": value}, headers=_bearer(token)
    )


def test_linking_a_steam_profile_stores_its_steam_id(
    client, viewer_access_token: str, viewer_user: User, steam_achievements
):
    response = _link_steam(
        client,
        viewer_access_token,
        viewer_user,
        "https://steamcommunity.com/id/gabelogannewell",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["steam_id"] == STEAM_ID
    steam_achievements.resolve_profile.assert_awaited_once_with(
        "https://steamcommunity.com/id/gabelogannewell"
    )


def test_relinking_another_profile_drops_the_old_progression(
    client, viewer_access_token: str, viewer_user: User, steam_achievements
):
    db_user_handler.update_user(
        viewer_user.id,
        {"steam_id": "76561197960265728", "steam_progression": {"total": 1}},
    )

    response = _link_steam(client, viewer_access_token, viewer_user, STEAM_ID)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["steam_progression"] == {}


def test_relinking_the_same_profile_keeps_its_progression(
    client, viewer_access_token: str, viewer_user: User, steam_achievements
):
    progression = {"total": 0, "results": []}
    db_user_handler.update_user(
        viewer_user.id, {"steam_id": STEAM_ID, "steam_progression": progression}
    )

    response = _link_steam(client, viewer_access_token, viewer_user, STEAM_ID)

    assert response.json()["steam_progression"] == progression
    steam_achievements.can_read_games.assert_not_awaited()


def test_a_blank_steam_id_unlinks_the_profile(
    client, viewer_access_token: str, viewer_user: User
):
    db_user_handler.update_user(
        viewer_user.id, {"steam_id": STEAM_ID, "steam_progression": {"total": 0}}
    )

    response = _link_steam(client, viewer_access_token, viewer_user, "")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["steam_id"] is None
    assert response.json()["steam_progression"] == {}


@pytest.mark.parametrize(
    ("resolved", "readable", "detail"),
    [
        (None, True, "No Steam profile matches this ID or URL"),
        (STEAM_ID, False, STEAM_GAME_DETAILS_PRIVATE),
    ],
    ids=["unknown-profile", "private-game-details"],
)
def test_linking_refuses_a_profile_it_cannot_read(
    client,
    viewer_access_token: str,
    viewer_user: User,
    steam_achievements,
    resolved,
    readable,
    detail,
):
    steam_achievements.resolve_profile.return_value = resolved
    steam_achievements.can_read_games.return_value = readable

    response = _link_steam(client, viewer_access_token, viewer_user, "gabe")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == detail
    unchanged = db_user_handler.get_user(viewer_user.id)
    assert unchanged and unchanged.steam_id is None


def test_linking_needs_steam_achievements_enabled(
    client, viewer_access_token: str, viewer_user: User, mocker
):
    mocker.patch.object(SteamHandler, "achievements_enabled", return_value=False)

    response = _link_steam(client, viewer_access_token, viewer_user, STEAM_ID)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == STEAM_ACHIEVEMENTS_DISABLED


def test_refreshing_steam_achievements_syncs_the_user(
    client, viewer_access_token: str, viewer_user: User, steam_achievements, mocker
):
    db_user_handler.update_user(viewer_user.id, {"steam_id": STEAM_ID})
    sync = mocker.patch("endpoints.user.sync_user_progress", AsyncMock())

    response = client.post(
        f"/api/users/{viewer_user.id}/steam/refresh",
        json={"incremental": True},
        headers=_bearer(viewer_access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert sync.await_args.args[0].id == viewer_user.id
    assert sync.await_args.kwargs == {"incremental": True}


def test_refreshing_a_private_profile_explains_why_it_failed(
    client, viewer_access_token: str, viewer_user: User, steam_achievements, mocker
):
    db_user_handler.update_user(viewer_user.id, {"steam_id": STEAM_ID})
    mocker.patch(
        "endpoints.user.sync_user_progress",
        AsyncMock(side_effect=SteamGameDetailsPrivateError(STEAM_ID)),
    )

    response = client.post(
        f"/api/users/{viewer_user.id}/steam/refresh",
        headers=_bearer(viewer_access_token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == STEAM_GAME_DETAILS_PRIVATE


def test_refreshing_without_a_linked_profile_is_not_found(
    client, viewer_access_token: str, viewer_user: User, steam_achievements
):
    response = client.post(
        f"/api/users/{viewer_user.id}/steam/refresh",
        headers=_bearer(viewer_access_token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_another_users_steam_achievements_cannot_be_refreshed(
    client, viewer_access_token: str, editor_user: User, steam_achievements
):
    db_user_handler.update_user(editor_user.id, {"steam_id": STEAM_ID})

    response = client.post(
        f"/api/users/{editor_user.id}/steam/refresh",
        headers=_bearer(viewer_access_token),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
