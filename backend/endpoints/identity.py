import secrets
import base64
import binascii
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel, BaseConfig
from starlette.authentication import requires

from handler import dbh
from models.user import User, Role
from utils.cache import cache
from utils.auth import (
    authenticate_user,
    get_password_hash,
)

router = APIRouter()



class UserSchema(BaseModel):
    username: str
    disabled: bool
    role: Role

    class Config(BaseConfig):
        orm_mode = True


def credentials_exception():
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Basic"},
    )


@router.post("/login")
def login(request: Request):
    if "Authorization" not in request.headers:
        raise credentials_exception()

    auth = request.headers["Authorization"]
    try:
        scheme, credentials = auth.split()
        if scheme.lower() != "basic":
            return
        decoded = base64.b64decode(credentials).decode("ascii")
    except (ValueError, UnicodeDecodeError, binascii.Error):
        raise credentials_exception()

    username, _, password = decoded.partition(":")
    user = authenticate_user(username, password)
    if not user:
        raise credentials_exception()

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
