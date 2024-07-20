import base64

import pytest
from fastapi.testclient import TestClient
from handler.redis_handler import cache
from main import app
from models.user import Role

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_cache():
    yield
    cache.flushall()


def test_login_logout(admin_user):
    response = client.get("/login")

    assert response.status_code == 405

    basic_auth = base64.b64encode(b"test_admin:test_admin_password").decode("ascii")
    response = client.post("/login", headers={"Authorization": f"Basic {basic_auth}"})

    assert response.status_code == 200
    assert response.cookies.get("romm_session")
    assert response.json()["msg"] == "Successfully logged in"

    response = client.post("/logout")

    assert response.status_code == 200
    assert response.json()["msg"] == "Successfully logged out"


def test_get_all_users(access_token):
    response = client.get("/users", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200

    users = response.json()
    assert len(users) == 1
    assert users[0]["username"] == "test_admin"


def test_get_user(access_token, editor_user):
    response = client.get(
        f"/users/{editor_user.id}", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200

    user = response.json()
    assert user["username"] == "test_editor"


def test_create_user(access_token):
    response = client.post(
        "/users",
        params={
            "username": "new_user",
            "password": "new_user_password",
            "role": "viewer",
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 201

    user = response.json()
    assert user["username"] == "new_user"
    assert user["role"] == "viewer"


def test_update_user(access_token, editor_user):
    assert editor_user.role == Role.EDITOR

    response = client.put(
        f"/users/{editor_user.id}",
        params={"username": "editor_user_new_username", "role": "viewer"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200

    user = response.json()
    assert user["role"] == "viewer"


def test_delete_user(access_token, editor_user):
    response = client.delete(
        f"/users/{editor_user.id}", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200

    body = response.json()
    assert body["msg"] == "User successfully deleted"
