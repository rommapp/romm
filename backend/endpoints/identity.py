import secrets
import base64
import binascii
from typing import Annotated
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, BaseConfig
from starlette.authentication import requires

from handler import dbh
from models.user import User, Role
from utils.cache import cache
from utils.auth import (
    authenticate_user,
    create_oauth_token,
    get_password_hash,
)

router = APIRouter()

ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


class UserSchema(BaseModel):
    username: str
    disabled: bool
    role: Role

    class Config(BaseConfig):
        orm_mode = True


def credentials_exception(scheme: str):
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": scheme},
    )


@router.post("/token")
def generate_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    if form_data.grant_type == "refresh_token":
        pass

    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise credentials_exception("Bearer")

    access_token = create_oauth_token(
        data={"sub": user.username, "type": "access"},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    refresh_token = create_oauth_token(
        data={"sub": user.username, "type": "refresh"},
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )

    # TODO add scopes to request

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/refresh_token")
def refresh_access_token(request: Request):
    if not request.user.is_authenticated:
        raise credentials_exception("Bearer")

    access_token = create_oauth_token(
        data={"sub": request.user.username, "type": "access"},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/login")
def login(request: Request):
    if "Authorization" not in request.headers:
        raise credentials_exception("Basic")

    auth = request.headers["Authorization"]
    try:
        scheme, credentials = auth.split()
        if scheme.lower() != "basic":
            return
        decoded = base64.b64decode(credentials).decode("ascii")
    except (ValueError, UnicodeDecodeError, binascii.Error):
        raise credentials_exception("Basic")

    username, _, password = decoded.partition(":")
    user = authenticate_user(username, password)
    if not user:
        raise credentials_exception("Basic")

    # Generate unique session key and store in cache
    request.session["session_id"] = secrets.token_hex(16)
    cache.set(f'romm:{request.session["session_id"]}', user.username)

    return {"message": "Successfully logged in"}


@router.get("/users")
@requires(["users.read"])
def users(request: Request) -> list[UserSchema]:
    return dbh.get_users()


@router.get("/users/me")
@requires(["me.read"])
def current_user(request: Request) -> UserSchema:
    return request.user


@router.post("/users/")
@requires(["users.write"])
def create_user(
    request: Request, username: str, password: str, role: str
) -> UserSchema:
    user = User(
        username=username,
        hashed_password=get_password_hash(password),
        disabled=False,
        role=Role[role.upper()],
    )
    dbh.add_user(user)

    return user
