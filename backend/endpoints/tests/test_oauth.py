from endpoints.auth import ACCESS_TOKEN_EXPIRE_MINUTES
from fastapi.exceptions import HTTPException
from fastapi.testclient import TestClient
from handler.auth.base_handler import WRITE_SCOPES
from main import app

client = TestClient(app)


def test_refreshing_oauth_token_basic(refresh_token):
    response = client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    assert response.status_code == 200

    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["expires"] == ACCESS_TOKEN_EXPIRE_MINUTES * 60


def test_refreshing_oauth_token_without_refresh_token():
    try:
        client.post(
            "/token",
            data={
                "grant_type": "refresh_token",
            },
        )
    except HTTPException as e:
        assert e.status_code == 400
        assert e.detail == "Missing refresh token"


def test_refreshing_oauth_token_with_invalid_refresh_token():
    try:
        client.post(
            "/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": "invalid_token",
            },
        )
    except HTTPException as e:
        assert e.status_code == 400
        assert e.detail == "Invalid refresh token"


def test_auth_via_upass(admin_user):
    response = client.post(
        "/token",
        data={
            "grant_type": "password",
            "username": "test_admin",
            "password": "test_admin_password",
        },
    )
    assert response.status_code == 200

    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["expires"] == ACCESS_TOKEN_EXPIRE_MINUTES * 60


def test_auth_via_upass_with_invalid_credentials(admin_user):
    try:
        client.post(
            "/token",
            data={
                "grant_type": "password",
                "username": "test_admin",
                "password": "a_bad_password",
            },
        )
    except HTTPException as e:
        assert e.status_code == 401
        assert e.detail == "Invalid username or password"


def test_auth_via_upass_with_excess_scopes(viewer_user):
    try:
        client.post(
            "/token",
            data={
                "grant_type": "password",
                "username": "test_viewer",
                "password": "test_viewer_password",
                "scopes": WRITE_SCOPES,
            },
        )
    except HTTPException as e:
        assert e.status_code == 403
        assert e.detail == "Insufficient scope"


def test_auth_with_invalid_grant_type():
    try:
        client.post(
            "/token",
            data={
                "grant_type": "invalid_type",
            },
        )
    except HTTPException as e:
        assert e.status_code == 400
        assert e.detail == "Invalid or unsupported grant type"
