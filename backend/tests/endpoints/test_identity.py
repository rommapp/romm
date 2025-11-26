import base64
from datetime import timedelta
from http import HTTPStatus
from unittest import mock

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from main import app

from endpoints.auth import ACCESS_TOKEN_EXPIRE_MINUTES
from handler.auth import oauth_handler
from handler.auth.middleware.redis_session_middleware import RedisSessionMiddleware
from handler.database.users_handler import DBUsersHandler
from handler.redis_handler import sync_cache
from models.user import Role, User


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def clear_cache():
    yield
    sync_cache.flushall()


def test_login_logout(client, admin_user: User):
    response = client.get("/api/login")

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    basic_auth = base64.b64encode(b"test_admin:test_admin_password").decode("ascii")
    response = client.post(
        "/api/login", headers={"Authorization": f"Basic {basic_auth}"}
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.cookies.get("romm_session")

    response = client.post("/api/logout")

    assert response.status_code == status.HTTP_200_OK


def test_get_all_users(client, access_token: str):
    response = client.get(
        "/api/users", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == status.HTTP_200_OK

    users = response.json()
    assert len(users) == 1
    assert users[0]["username"] == "test_admin"


def test_get_user(client, access_token: str, editor_user: User):
    response = client.get(
        f"/api/users/{editor_user.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK

    user = response.json()
    assert user["username"] == "test_editor"


@pytest.mark.parametrize("new_user_role", [Role.VIEWER, Role.EDITOR, Role.ADMIN])
def test_add_user_from_admin_user(client, access_token: str, new_user_role: Role):
    response = client.post(
        "/api/users",
        json={
            "username": "new_user",
            "password": "new_user_password",
            "email": "new_user@example.com",
            "role": new_user_role.value,
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == HTTPStatus.CREATED

    user = response.json()
    assert user["username"] == "new_user"
    assert user["role"] == new_user_role.value


@pytest.mark.parametrize(
    "fixture_requesting_user, existing_admin_users, expected_status_code",
    [
        ("editor_user", False, HTTPStatus.CREATED),
        ("editor_user", True, HTTPStatus.FORBIDDEN),
        ("viewer_user", False, HTTPStatus.CREATED),
        ("viewer_user", True, HTTPStatus.FORBIDDEN),
    ],
)
def test_add_user_from_unauthorized_user(
    request,
    client,
    admin_user: User,
    fixture_requesting_user: User,
    existing_admin_users: list[User],
    expected_status_code: int,
):
    requesting_user = request.getfixturevalue(fixture_requesting_user)

    data = {
        "sub": requesting_user.username,
        "iss": "romm:oauth",
        "scopes": " ".join(requesting_user.oauth_scopes),
        "type": "access",
    }
    access_token = oauth_handler.create_oauth_token(
        data=data, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    with mock.patch.object(
        DBUsersHandler,
        "get_admin_users",
        return_value=[admin_user] if existing_admin_users else [],
    ):
        response = client.post(
            "/api/users",
            json={
                "username": "new_user",
                "password": "new_user_password",
                "email": "new_user@example.com",
                "role": Role.VIEWER.value,
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == expected_status_code


def test_add_user_with_existing_username(client, access_token: str, admin_user: User):
    response = client.post(
        "/api/users",
        json={
            "username": admin_user.username,
            "password": "new_user_password",
            "email": "new_user@example.com",
            "role": Role.VIEWER.value,
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST

    response = response.json()
    assert response["detail"] == f"Username {admin_user.username} already exists"


def test_update_user(client, access_token: str, editor_user: User):
    assert editor_user.role == Role.EDITOR

    response = client.put(
        f"/api/users/{editor_user.id}",
        data={"username": "editor_user_new_username", "role": "viewer"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK

    user = response.json()
    assert user["role"] == "viewer"


def test_delete_user(client, access_token: str, editor_user: User):
    response = client.delete(
        f"/api/users/{editor_user.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_password_change_invalidates_sessions(client, admin_user: User):
    # Get the user's session cookie
    basic_auth = base64.b64encode(
        f"{admin_user.username}:test_admin_password".encode("ascii")
    ).decode("ascii")
    response = client.post(
        "/api/login", headers={"Authorization": f"Basic {basic_auth}"}
    )
    assert response.status_code == HTTPStatus.OK
    old_session_cookie = response.cookies.get("romm_session")
    assert old_session_cookie is not None

    # Verify session works
    response = client.get("/api/users/me", cookies={"romm_session": old_session_cookie})
    assert response.status_code == HTTPStatus.OK

    # Update the user's password
    response = client.put(
        f"/api/users/{admin_user.id}",
        data={"password": "new_admin_password"},
        headers={"Authorization": f"Basic {basic_auth}"},
    )
    assert response.status_code == HTTPStatus.OK

    # Attempt to access a protected resource using the old session cookie
    response = client.get("/api/users/me", cookies={"romm_session": old_session_cookie})
    assert response.status_code in [HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN]

    # Login with the new credentials
    basic_auth_new = base64.b64encode(
        f"{admin_user.username}:new_admin_password".encode("ascii")
    ).decode("ascii")
    response = client.post(
        "/api/login", headers={"Authorization": f"Basic {basic_auth_new}"}
    )
    assert response.status_code == HTTPStatus.OK
    new_session_cookie = response.cookies.get("romm_session")
    assert new_session_cookie is not None
    assert new_session_cookie != old_session_cookie

    # Attempt to access a protected resource using the new session cookie
    response = client.get("/api/users/me", cookies={"romm_session": new_session_cookie})
    assert response.status_code == HTTPStatus.OK

    await RedisSessionMiddleware.clear_user_sessions(admin_user.username)


@pytest.mark.asyncio
async def test_logout_invalidates_session(client, admin_user: User):
    # Get the user's session cookie
    basic_auth = base64.b64encode(
        f"{admin_user.username}:test_admin_password".encode("ascii")
    ).decode("ascii")
    response = client.post(
        "/api/login", headers={"Authorization": f"Basic {basic_auth}"}
    )
    assert response.status_code == HTTPStatus.OK
    session_cookie = response.cookies.get("romm_session")
    assert session_cookie is not None

    # Verify session works
    response = client.get("/api/users/me", cookies={"romm_session": session_cookie})
    assert response.status_code == HTTPStatus.OK

    # Log out the user
    response = client.post("/api/logout", cookies={"romm_session": session_cookie})
    assert response.status_code == HTTPStatus.OK

    # Attempt to access a protected resource using the old session cookie
    response = client.get("/api/users/me", cookies={"romm_session": session_cookie})
    assert response.status_code in [HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN]

    await RedisSessionMiddleware.clear_user_sessions(admin_user.username)
