import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Request, status
from fastapi.exceptions import HTTPException
from joserfc import jwt

from decorators.auth import protected_route
from exceptions.auth_exceptions import OAuthCredentialsException, UserDisabledException
from handler.auth.base_handler import oauth_handler, oct_key
from handler.auth.constants import ALGORITHM
from handler.database import db_user_handler
from handler.redis_handler import redis_client
from models.user import User
from utils.router import APIRouter


def test_create_oauth_token():
    token = oauth_handler.create_access_token(data={"sub": "test_user"})

    assert isinstance(token, str)


async def test_get_current_active_user_from_bearer_token(admin_user):
    token = oauth_handler.create_access_token(
        data={
            "sub": admin_user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(admin_user.oauth_scopes),
        },
    )
    user, claims = await oauth_handler.get_current_active_user_from_bearer_token(token)
    if not user or not claims:
        pytest.fail("User or claims not found")

    assert user.id == admin_user.id
    assert claims["sub"] == admin_user.username
    assert claims["iss"] == "romm:oauth"
    assert set(claims["scopes"].split()).issubset(admin_user.oauth_scopes)
    assert claims["type"] == "access"


async def test_get_current_active_user_from_bearer_token_invalid_token():
    with pytest.raises(HTTPException):
        await oauth_handler.get_current_active_user_from_bearer_token("invalid_token")


async def test_get_current_active_user_from_bearer_token_invalid_user():
    token = oauth_handler.create_access_token(
        data={"sub": "invalid_user", "iss": "romm:oauth"}
    )

    with pytest.raises(HTTPException):
        await oauth_handler.get_current_active_user_from_bearer_token(token)


async def test_get_current_active_user_from_bearer_token_disabled_user(admin_user):
    token = oauth_handler.create_access_token(
        data={
            "sub": admin_user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(admin_user.oauth_scopes),
        },
    )

    db_user_handler.update_user(admin_user.id, {"enabled": False})

    try:
        await oauth_handler.get_current_active_user_from_bearer_token(token)
    except HTTPException as e:
        assert e.status_code == status.HTTP_401_UNAUTHORIZED
        assert e.detail == "Disabled user"


async def test_get_current_active_user_from_bearer_token_expired_token(admin_user):
    token = oauth_handler.create_access_token(
        data={
            "sub": admin_user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(admin_user.oauth_scopes),
        },
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(HTTPException) as exc:
        await oauth_handler.get_current_active_user_from_bearer_token(token)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


def _live_refresh_token(claims: dict[str, str]) -> str:
    """Sign a token whose jti is registered in Redis, so only the given claims can reject it."""
    jti = str(uuid.uuid4())
    expire = int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp())
    redis_client.set(f"refresh-jti:{jti}", "valid", ex=300)
    return jwt.encode(
        {"alg": ALGORITHM}, {**claims, "jti": jti, "exp": expire}, oct_key
    )


async def test_consume_refresh_token_rejects_foreign_issuer(admin_user: User):
    token = _live_refresh_token(
        {"sub": admin_user.username, "iss": "someone-else", "type": "refresh"}
    )

    with pytest.raises(HTTPException) as exc:
        await oauth_handler.consume_refresh_token(token)

    assert exc.value is OAuthCredentialsException


async def test_consume_refresh_token_rejects_access_token(admin_user: User):
    token = _live_refresh_token(
        {"sub": admin_user.username, "iss": "romm:oauth", "type": "access"}
    )

    with pytest.raises(HTTPException) as exc:
        await oauth_handler.consume_refresh_token(token)

    assert exc.value is OAuthCredentialsException


async def test_consume_refresh_token_rejects_missing_subject():
    token = oauth_handler.create_refresh_token(
        data={"iss": "romm:oauth"}, expires_delta=timedelta(minutes=5)
    )

    with pytest.raises(HTTPException) as exc:
        await oauth_handler.consume_refresh_token(token)

    assert exc.value is OAuthCredentialsException


async def test_consume_refresh_token_rejects_deleted_user(admin_user: User):
    token = oauth_handler.create_refresh_token(
        data={"sub": admin_user.username, "iss": "romm:oauth"},
        expires_delta=timedelta(minutes=5),
    )
    db_user_handler.delete_user(admin_user.id)

    with pytest.raises(HTTPException) as exc:
        await oauth_handler.consume_refresh_token(token)

    assert exc.value is OAuthCredentialsException


async def test_consume_refresh_token_rejects_disabled_user(admin_user: User):
    token = oauth_handler.create_refresh_token(
        data={"sub": admin_user.username, "iss": "romm:oauth"},
        expires_delta=timedelta(minutes=5),
    )
    db_user_handler.update_user(admin_user.id, {"enabled": False})

    with pytest.raises(HTTPException) as exc:
        await oauth_handler.consume_refresh_token(token)

    assert exc.value is UserDisabledException


def test_protected_route():
    router = APIRouter()

    @protected_route(router.get, "/test")
    def test_route(request: Request):
        return {"test": "test"}

    req = Request({"type": "http", "method": "GET", "url": "/test"})

    assert test_route(req) == {"test": "test"}
