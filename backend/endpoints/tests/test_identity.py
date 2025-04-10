import base64
from datetime import timedelta
from http import HTTPStatus
from unittest import mock

import pytest
from endpoints.auth import ACCESS_TOKEN_EXPIRE_MINUTES
from fastapi.testclient import TestClient
from handler.auth import oauth_handler
from handler.database.users_handler import DBUsersHandler
from handler.redis_handler import sync_cache
from main import app
from models.user import Role


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def clear_cache():
    yield
    sync_cache.flushall()


def test_login_logout(client, admin_user):
    response = client.get("/api/login")

    assert response.status_code == 405

    basic_auth = base64.b64encode(b"test_admin:test_admin_password").decode("ascii")
    response = client.post(
        "/api/login", headers={"Authorization": f"Basic {basic_auth}"}
    )

    assert response.status_code == 200
    assert response.cookies.get("romm_session")
    assert response.json()["msg"] == "Successfully logged in"

    response = client.post("/api/logout")

    assert response.status_code == 200
    assert response.json()["msg"] == "Successfully logged out"


def test_get_all_users(client, access_token):
    response = client.get(
        "/api/users", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200

    users = response.json()
    assert len(users) == 1
    assert users[0]["username"] == "test_admin"


def test_get_user(client, access_token, editor_user):
    response = client.get(
        f"/api/users/{editor_user.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200

    user = response.json()
    assert user["username"] == "test_editor"


@pytest.mark.parametrize("new_user_role", [Role.VIEWER, Role.EDITOR, Role.ADMIN])
def test_add_user_from_admin_user(client, access_token, new_user_role):
    response = client.post(
        "/api/users",
        params={
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
    admin_user,
    fixture_requesting_user,
    existing_admin_users,
    expected_status_code,
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
            params={
                "username": "new_user",
                "password": "new_user_password",
                "email": "new_user@example.com",
                "role": Role.VIEWER.value,
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == expected_status_code


def test_add_user_with_existing_username(client, access_token, admin_user):
    response = client.post(
        "/api/users",
        params={
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


def test_update_user(client, access_token, editor_user):
    assert editor_user.role == Role.EDITOR

    response = client.put(
        f"/api/users/{editor_user.id}",
        params={"username": "editor_user_new_username", "role": "viewer"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200

    user = response.json()
    assert user["role"] == "viewer"


def test_delete_user(client, access_token, editor_user):
    response = client.delete(
        f"/api/users/{editor_user.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["msg"] == "User successfully deleted"
