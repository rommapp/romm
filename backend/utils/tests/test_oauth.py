import pytest
from fastapi import APIRouter, Request
from fastapi.exceptions import HTTPException

from handler import dbh
from ..oauth import (
    create_oauth_token,
    get_current_active_user_from_bearer_token,
    protected_route,
)


def test_create_oauth_token():
    token = create_oauth_token({"sub": "test_user"})

    assert isinstance(token, str)


async def test_get_current_active_user_from_bearer_token(admin_user):
    token = create_oauth_token(
        {
            "sub": admin_user.username,
            "scopes": " ".join(admin_user.oauth_scopes),
            "type": "access",
        },
    )
    user, payload = await get_current_active_user_from_bearer_token(token)

    assert user.id == admin_user.id
    assert payload["sub"] == admin_user.username
    assert set(payload["scopes"].split()).issubset(admin_user.oauth_scopes)
    assert payload["type"] == "access"


async def test_get_current_active_user_from_bearer_token_invalid_token():
    with pytest.raises(HTTPException):
        await get_current_active_user_from_bearer_token("invalid_token")


async def test_get_current_active_user_from_bearer_token_invalid_user():
    token = create_oauth_token({"sub": "invalid_user"})

    with pytest.raises(HTTPException):
        await get_current_active_user_from_bearer_token(token)


async def test_get_current_active_user_from_bearer_token_disabled_user(admin_user):
    token = create_oauth_token(
        {
            "sub": admin_user.username,
            "scopes": " ".join(admin_user.oauth_scopes),
            "type": "access",
        },
    )

    dbh.update_user(admin_user.id, {"enabled": False})

    try:
        await get_current_active_user_from_bearer_token(token)
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
