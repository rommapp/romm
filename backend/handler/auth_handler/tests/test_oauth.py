import pytest
from fastapi import APIRouter, Request
from fastapi.exceptions import HTTPException

from decorators.auth import protected_route
from handler.auth_handler import oauth_handler
from handler.db_handler import db_users_handler


def test_create_oauth_token():
    token = oauth_handler.create_oauth_token(data={"sub": "test_user"})

    assert isinstance(token, str)


async def test_get_current_active_user_from_bearer_token(admin_user):
    token = oauth_handler.create_oauth_token(
        data={
            "sub": admin_user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(admin_user.oauth_scopes),
            "type": "access",
        },
    )
    user, payload = await oauth_handler.get_current_active_user_from_bearer_token(token)

    assert user.id == admin_user.id
    assert payload["sub"] == admin_user.username
    assert payload["iss"] == "romm:oauth"
    assert set(payload["scopes"].split()).issubset(admin_user.oauth_scopes)
    assert payload["type"] == "access"


async def test_get_current_active_user_from_bearer_token_invalid_token():
    with pytest.raises(HTTPException):
        await oauth_handler.get_current_active_user_from_bearer_token("invalid_token")


async def test_get_current_active_user_from_bearer_token_invalid_user():
    token = oauth_handler.create_oauth_token(
        data={"sub": "invalid_user", "iss": "romm:oauth"}
    )

    with pytest.raises(HTTPException):
        await oauth_handler.get_current_active_user_from_bearer_token(token)


async def test_get_current_active_user_from_bearer_token_disabled_user(admin_user):
    token = oauth_handler.create_oauth_token(
        data={
            "sub": admin_user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(admin_user.oauth_scopes),
            "type": "access",
        },
    )

    db_users_handler.update_user(admin_user.id, {"enabled": False})

    try:
        await oauth_handler.get_current_active_user_from_bearer_token(token)
    except HTTPException as e:
        assert e.status_code == 401
        assert e.detail == "Inactive user"


def test_protected_route():
    router = APIRouter()

    @protected_route(router.get, "/test")
    def test_route(request: Request):
        return {"test": "test"}

    req = Request({"type": "http", "method": "GET", "url": "/test"})

    assert test_route(req) == {"test": "test"}
