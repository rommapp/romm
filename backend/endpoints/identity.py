import os
import secrets
import base64
import binascii
from typing import Optional, Annotated
from fastapi import APIRouter, HTTPException, status, Request, Depends
from fastapi.security.http import HTTPBasic
from pydantic import BaseModel, BaseConfig
from starlette.authentication import requires

from handler import dbh
from models.user import User, Role
from utils.cache import cache
from utils.auth import authenticate_user, get_password_hash
from utils.oauth import protected_route

router = APIRouter()


class UserSchema(BaseModel):
    username: str
    disabled: bool
    role: Role

    class Config(BaseConfig):
        orm_mode = True


credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Incorrect username or password",
    headers={"WWW-Authenticate": "Basic"},
)


@router.post("/login", dependencies=[Depends(HTTPBasic(auto_error=False))])
def login(request: Request):

    if not os.environ.get("ROMM_AUTH_ENABLED"):
        return {"message": "RomM auth not enabled."}

    if "Authorization" not in request.headers:
        raise credentials_exception

    auth = request.headers["Authorization"]
    try:
        scheme, credentials = auth.split()
        if scheme.lower() != "basic":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme",
                headers={"WWW-Authenticate": "Basic"},
            )
        decoded = base64.b64decode(credentials).decode("ascii")
    except (ValueError, UnicodeDecodeError, binascii.Error):
        raise credentials_exception

    username, _, password = decoded.partition(":")
    user = authenticate_user(username, password)
    if not user:
        raise credentials_exception

    # Generate unique session key and store in cache
    request.session["session_id"] = secrets.token_hex(16)
    cache.set(f'romm:{request.session["session_id"]}', user.username)

    return {"message": "Successfully logged in"}


@router.post("/logout")
def logout(request: Request):
    # Check if session key already stored in cache
    session_id = request.session.get("session_id")
    if not session_id:
        return {"message": "Already logged out"}

    if not request.user.id:
        return {"message": "Already logged out"}

    cache.delete(f"romm:{session_id}")
    request.session["session_id"] = None

    return {"message": "Successfully logged out"}


@protected_route(router.get, "/users", ["users.read"])
@requires(["users.read"])
def users(request: Request) -> list[UserSchema]:
    return dbh.get_users()


@protected_route(router.get, "/users/me", ["me.read"])
@requires(["me.read"])
def current_user(request: Request) -> UserSchema:
    return request.user


@protected_route(router.get, "/users/{user_id}", ["users.read"])
@requires(["users.read"])
def get_user(request: Request, user_id: int) -> UserSchema:
    user = dbh.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@protected_route(
    router.post,
    "/users",
    ["users.write"],
    status_code=status.HTTP_201_CREATED,
)
@requires(["users.write"])
def create_user(
    request: Request, username: str, password: str, role: str
) -> UserSchema:
    user = User(
        username=username,
        hashed_password=get_password_hash(password),
        role=Role[role.upper()],
    )

    return dbh.add_user(user)


class UserUpdateForm:
    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        role: Optional[str] = None,
        disabled: Optional[bool] = None,
    ):
        self.username = username
        self.password = password
        self.role = role
        self.disabled = disabled


@protected_route(router.patch, "/users/{user_id}", ["users.write"])
@requires(["users.write"])
def update_user(
    request: Request, user_id: int, form_data: Annotated[UserUpdateForm, Depends()]
) -> UserSchema:
    user = dbh.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    cleaned_data = {}

    if form_data.username:
        existing_user = dbh.get_user_by_username(form_data.username.lower())
        if existing_user:
            raise HTTPException(
                status_code=400, detail="Username already in use by another user"
            )

        cleaned_data["username"] = form_data.username.lower()

    if form_data.password:
        cleaned_data["hashed_password"] = get_password_hash(form_data.password)

    # You can't change your own role
    if form_data.role and request.user.id != user_id:
        cleaned_data["role"] = Role[form_data.role.upper()]

    if form_data.disabled is not None:
        cleaned_data["disabled"] = form_data.disabled

    if not cleaned_data:
        raise HTTPException(
            status_code=400, detail="No valid fields to update were provided"
        )

    dbh.update_user(user_id, cleaned_data)

    # Log out the current user if username or password changed
    if cleaned_data.get("username") or cleaned_data.get("hashed_password"):
        session_id = request.session.get("session_id")
        if session_id:
            cache.delete(f"romm:{session_id}")
            request.session["session_id"] = None

    return dbh.get_user(user_id)


@protected_route(router.delete, "/users/{user_id}", ["users.write"])
def delete_user(request: Request, user_id: int):
    user = dbh.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # You can't delete the user you're logged in as
    if request.user.id == user_id:
        raise HTTPException(status_code=400, detail="You cannot delete yourself")

    # You can't delete the last admin user
    if user.role == Role.ADMIN and len(dbh.get_admin_users()) == 1:
        raise HTTPException(
            status_code=400, detail="You cannot delete the last admin user"
        )

    dbh.delete_user(user_id)

    return {"message": "User successfully deleted"}
