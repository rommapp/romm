import base64
import time
from http import HTTPStatus
from unittest import mock

import httpx2
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from joserfc import jwt
from joserfc.jwk import OctKey
from tests.audit_events import recorded_events

from handler.auth import base_handler as auth_handler_module
from handler.auth.base_handler import auth_handler, oidc_handler
from handler.auth.constants import ALGORITHM, SESSION_COOKIE_NAME
from handler.database import db_user_handler
from handler.redis_handler import redis_client
from models.user import User


def _basic(username: str, password: str) -> dict[str, str]:
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


def _reset_password(client, token: str, new_password: str = "a_new_password"):
    return client.post(
        "/api/reset-password", json={"token": token, "new_password": new_password}
    )


def test_reset_password_with_a_valid_token(client, admin_user: User):
    token = auth_handler.generate_password_reset_token(admin_user)

    response = _reset_password(client, token)

    assert response.status_code == status.HTTP_200_OK
    old = client.post("/api/login", headers=_basic("test_admin", "test_admin_password"))
    new = client.post("/api/login", headers=_basic("test_admin", "a_new_password"))
    assert old.status_code == status.HTTP_401_UNAUTHORIZED
    assert new.status_code == status.HTTP_200_OK
    assert "auth.password_reset" in [event.action for event in recorded_events()]


def test_reset_password_token_works_once(client, admin_user: User):
    token = auth_handler.generate_password_reset_token(admin_user)
    assert _reset_password(client, token).status_code == status.HTTP_200_OK

    response = _reset_password(client, token, "another_password")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert client.post(
        "/api/login", headers=_basic("test_admin", "another_password")
    ).status_code == (status.HTTP_401_UNAUTHORIZED)


def test_reset_password_rejects_a_malformed_token(client):
    assert _reset_password(client, "not-a-jwt").status_code == (
        status.HTTP_400_BAD_REQUEST
    )


def test_reset_password_rejects_a_token_signed_with_another_key(
    client, admin_user: User
):
    forged = jwt.encode(
        {"alg": ALGORITHM},
        {"sub": admin_user.username, "type": "reset", "jti": "forged"},
        OctKey.import_key("not-the-server-secret-key-not-the-server"),
    )
    redis_client.set("reset-jti:forged", "valid", ex=60)

    assert _reset_password(client, forged).status_code == (status.HTTP_400_BAD_REQUEST)


def test_reset_password_rejects_a_token_for_another_purpose(client, admin_user: User):
    invite = jwt.encode(
        {"alg": ALGORITHM},
        {
            "sub": admin_user.username,
            "type": "invite",
            "jti": "invite",
            "exp": int(time.time()) + 60,
        },
        auth_handler_module.oct_key,
    )
    redis_client.set("reset-jti:invite", "valid", ex=60)

    response = _reset_password(client, invite)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Invalid token purpose"


def test_reset_password_rejects_an_expired_token(client, admin_user: User):
    expired = jwt.encode(
        {"alg": ALGORITHM},
        {
            "sub": admin_user.username,
            "type": "reset",
            "jti": "expired",
            "exp": int(time.time()) - 1,
        },
        auth_handler_module.oct_key,
    )
    redis_client.set("reset-jti:expired", "valid", ex=60)

    response = _reset_password(client, expired)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Token has expired"


def test_reset_password_for_a_deleted_user_is_not_found(client, viewer_user: User):
    token = auth_handler.generate_password_reset_token(viewer_user)
    db_user_handler.delete_user(viewer_user.id)

    assert _reset_password(client, token).status_code == status.HTTP_404_NOT_FOUND


def _oidc_callback(client: TestClient, user: User | None) -> httpx2.Response:
    fake_oauth = mock.MagicMock()
    fake_oauth.openid.authorize_access_token = mock.AsyncMock(
        return_value={"id_token": "provider-id-token"}
    )
    with (
        mock.patch("endpoints.auth.OIDC_ENABLED", True),
        mock.patch("endpoints.auth.OIDC_RP_INITIATED_LOGOUT", True),
        mock.patch("endpoints.auth.oauth", fake_oauth),
        mock.patch.object(
            oidc_handler,
            "get_current_active_user_from_openid_token",
            mock.AsyncMock(return_value=(user, {})),
        ),
    ):
        return client.get("/api/oauth/openid?code=c&state=s", follow_redirects=False)


def test_oidc_callback_logs_the_user_in(client: TestClient, admin_user: User):
    response = _oidc_callback(client, admin_user)

    assert response.status_code == HTTPStatus.TEMPORARY_REDIRECT
    assert response.headers["location"] == "/"
    session_cookie = response.cookies.get(SESSION_COOKIE_NAME)
    assert session_cookie is not None
    cookie_header = {"Cookie": f"{SESSION_COOKIE_NAME}={session_cookie}"}
    me = client.get("/api/users/me", headers=cookie_header)
    assert me.status_code == status.HTTP_200_OK
    assert me.json()["username"] == "test_admin"

    updated = db_user_handler.get_user(admin_user.id)
    assert updated and updated.last_login is not None
    [event] = recorded_events()
    assert (event.action, event.data["method"]) == ("auth.login", "oidc")
    assert event.device_id is not None

    with (
        mock.patch("endpoints.auth.OIDC_RP_INITIATED_LOGOUT", True),
        mock.patch(
            "endpoints.auth.OIDC_END_SESSION_ENDPOINT", "https://idp.example/logout"
        ),
    ):
        logout = client.post("/api/logout", headers=cookie_header)
    assert "id_token_hint=provider-id-token" in logout.json()["oidc_logout_url"]


def test_oidc_callback_for_an_unknown_user_is_unauthorized(client: TestClient):
    response = _oidc_callback(client, None)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert SESSION_COOKIE_NAME not in response.cookies
    [event] = recorded_events()
    assert (event.action, event.data["reason"]) == ("auth.login_failed", "credentials")


def test_oidc_callback_for_a_disabled_user_is_unauthorized(
    client: TestClient, viewer_user: User
):
    db_user_handler.update_user(viewer_user.id, {"enabled": False})
    disabled = db_user_handler.get_user(viewer_user.id)

    response = _oidc_callback(client, disabled)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert SESSION_COOKIE_NAME not in response.cookies
    [event] = recorded_events()
    assert (event.action, event.data["reason"]) == ("auth.login_failed", "disabled")


@pytest.mark.parametrize("path", ["/api/login/openid", "/api/oauth/openid"])
def test_oidc_endpoints_refuse_when_oidc_is_disabled(client: TestClient, path: str):
    with mock.patch("endpoints.auth.OIDC_ENABLED", False):
        response = client.get(path, follow_redirects=False)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json()["detail"] == "OAuth disabled"
