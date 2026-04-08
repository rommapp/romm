from fastapi import status
from fastapi.exceptions import HTTPException

from config import OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS
from handler.auth.constants import EDIT_SCOPES


def test_refreshing_oauth_token_basic(client, refresh_token):
    response = client.post(
        "/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["expires"] == OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS


def test_refreshing_oauth_token_without_refresh_token(client):
    try:
        client.post(
            "/api/token",
            data={
                "grant_type": "refresh_token",
            },
        )
    except HTTPException as e:
        assert e.status_code == status.HTTP_400_BAD_REQUEST
        assert e.detail == "Missing refresh token"


def test_refreshing_oauth_token_with_invalid_refresh_token(client):
    try:
        client.post(
            "/api/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": "invalid_token",
            },
        )
    except HTTPException as e:
        assert e.status_code == status.HTTP_400_BAD_REQUEST
        assert e.detail == "Invalid refresh token"


def test_refresh_token_rotation_invalidates_old_token(client, refresh_token):
    first_response = client.post(
        "/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )

    assert first_response.status_code == status.HTTP_200_OK
    first_body = first_response.json()

    assert first_body["access_token"]
    assert first_body["refresh_token"]
    assert first_body["refresh_token"] != refresh_token

    new_refresh_token = first_body["refresh_token"]

    second_response = client.post(
        "/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )

    assert second_response.status_code == status.HTTP_401_UNAUTHORIZED

    third_response = client.post(
        "/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": new_refresh_token,
        },
    )

    assert third_response.status_code == status.HTTP_200_OK


def test_auth_via_upass(client, admin_user):
    response = client.post(
        "/api/token",
        data={
            "grant_type": "password",
            "username": "test_admin",
            "password": "test_admin_password",
        },
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["expires"] == OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS


def test_auth_via_upass_with_invalid_credentials(client, admin_user):
    try:
        client.post(
            "/api/token",
            data={
                "grant_type": "password",
                "username": "test_admin",
                "password": "a_bad_password",
            },
        )
    except HTTPException as e:
        assert e.status_code == status.HTTP_401_UNAUTHORIZED
        assert e.detail == "Invalid username or password"


def test_auth_via_upass_with_excess_scopes(client, viewer_user):
    try:
        client.post(
            "/api/token",
            data={
                "grant_type": "password",
                "username": "test_viewer",
                "password": "test_viewer_password",
                "scopes": EDIT_SCOPES,
            },
        )
    except HTTPException as e:
        assert e.status_code == status.HTTP_403_FORBIDDEN
        assert e.detail == "Insufficient scope"


def test_auth_with_invalid_grant_type(client):
    try:
        client.post(
            "/api/token",
            data={
                "grant_type": "invalid_type",
            },
        )
    except HTTPException as e:
        assert e.status_code == status.HTTP_400_BAD_REQUEST
        assert e.detail == "Invalid or unsupported grant type"


def test_refreshing_oauth_token_expired_refresh_token(
    client, admin_user, expired_refresh_token
):
    response = client.post(
        "/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": expired_refresh_token,
        },
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
