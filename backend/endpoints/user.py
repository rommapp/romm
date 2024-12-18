from pathlib import Path
from typing import Annotated

from anyio import open_file
from config import ASSETS_BASE_PATH
from decorators.auth import protected_route
from endpoints.forms.identity import UserForm
from endpoints.responses import MessageResponse
from endpoints.responses.identity import UserSchema
from fastapi import Depends, HTTPException, Request, status
from handler.auth import auth_handler
from handler.auth.base_handler import Scope
from handler.database import db_user_handler
from handler.filesystem import fs_asset_handler
from logger.logger import log
from models.user import Role, User
from utils.router import APIRouter

router = APIRouter()


@protected_route(
    router.post,
    "/users",
    [],
    status_code=status.HTTP_201_CREATED,
)
def add_user(
    request: Request, username: str, password: str, email: str, role: str
) -> UserSchema:
    """Create user endpoint

    Args:
        request (Request): Fastapi Requests object
        username (str): User username
        password (str): User password
        email (str): User email
        role (str): RomM Role object represented as string

    Returns:
        UserSchema: Newly created user
    """

    # If there are admin users already, enforce the USERS_WRITE scope.
    if (
        Scope.USERS_WRITE not in request.auth.scopes
        and len(db_user_handler.get_admin_users()) > 0
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    existing_user_by_username = db_user_handler.get_user_by_username(username.lower())
    if existing_user_by_username:
        msg = f"Username {username.lower()} already exists"
        log.error(msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    existing_user_by_email = db_user_handler.get_user_by_email(email.lower())
    if existing_user_by_email:
        msg = f"Uesr with email {email.lower()} already exists"
        log.error(msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    user = User(
        username=username.lower(),
        hashed_password=auth_handler.get_password_hash(password),
        email=email.lower(),
        role=Role[role.upper()],
    )

    return db_user_handler.add_user(user)


@protected_route(router.get, "/users", [Scope.USERS_READ])
def get_users(request: Request) -> list[UserSchema]:
    """Get all users endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        list[UserSchema]: All users stored in the RomM's database
    """

    return [u for u in db_user_handler.get_users()]


@protected_route(router.get, "/users/me", [Scope.ME_READ])
def get_current_user(request: Request) -> UserSchema | None:
    """Get current user endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        UserSchema | None: Current user
    """

    return request.user


@protected_route(router.get, "/users/{id}", [Scope.USERS_READ])
def get_user(request: Request, id: int) -> UserSchema:
    """Get user endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        UserSchem: User stored in the RomM's database
    """

    user = db_user_handler.get_user(id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@protected_route(router.put, "/users/{id}", [Scope.ME_WRITE])
async def update_user(
    request: Request, id: int, form_data: Annotated[UserForm, Depends()]
) -> UserSchema:
    """Update user endpoint

    Args:
        request (Request): Fastapi Requests object
        user_id (int): User internal id
        form_data (Annotated[UserUpdateForm, Depends): Form Data with user updated info

    Raises:
        HTTPException: User is not found in database
        HTTPException: Username already in use by another user

    Returns:
        UserSchema: Updated user info
    """

    db_user = db_user_handler.get_user(id)
    if not db_user:
        msg = f"Username with id {id} not found"
        log.error(msg)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)

    # Admin users can edit any user, while other users can only edit self
    if db_user.id != request.user.id and request.user.role != Role.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    cleaned_data = {}

    if form_data.username and form_data.username != db_user.username:
        existing_user = db_user_handler.get_user_by_username(form_data.username.lower())
        if existing_user:
            msg = f"Username {form_data.username} already exists"
            log.error(msg)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=msg,
            )

        cleaned_data["username"] = form_data.username.lower()

    if form_data.password:
        cleaned_data["hashed_password"] = auth_handler.get_password_hash(
            form_data.password
        )

    if form_data.email and form_data.email != db_user.email:
        existing_user = db_user_handler.get_user_by_email(form_data.email.lower())
        if existing_user:
            msg = f"User with email {form_data.email} already exists"
            log.error(msg)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=msg,
            )

        cleaned_data["email"] = form_data.email.lower()

    # You can't change your own role
    if form_data.role and request.user.id != id:
        cleaned_data["role"] = Role[form_data.role.upper()]  # type: ignore[assignment]

    # You can't disable yourself
    if form_data.enabled is not None and request.user.id != id:
        cleaned_data["enabled"] = form_data.enabled  # type: ignore[assignment]

    if form_data.avatar is not None:
        user_avatar_path = fs_asset_handler.build_avatar_path(user=db_user)
        file_location = f"{user_avatar_path}/{form_data.avatar.filename}"
        cleaned_data["avatar_path"] = file_location
        Path(f"{ASSETS_BASE_PATH}/{user_avatar_path}").mkdir(
            parents=True, exist_ok=True
        )
        async with await open_file(
            f"{ASSETS_BASE_PATH}/{file_location}", "wb+"
        ) as file_object:
            await file_object.write(form_data.avatar.file.read())

    if cleaned_data:
        db_user_handler.update_user(id, cleaned_data)

        # Log out the current user if username or password changed
        creds_updated = cleaned_data.get("username") or cleaned_data.get(
            "hashed_password"
        )
        if request.user.id == id and creds_updated:
            request.session.clear()

    return db_user_handler.get_user(id)


@protected_route(router.delete, "/users/{id}", [Scope.USERS_WRITE])
def delete_user(request: Request, id: int) -> MessageResponse:
    """Delete user endpoint

    Args:
        request (Request): Fastapi Request object
        user_id (int): User internal id

    Raises:
        HTTPException: User is not found in database
        HTTPException: User deleting itself
        HTTPException: User is the last admin user

    Returns:
        MessageResponse: Standard message response
    """

    user = db_user_handler.get_user(id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # You can't delete the user you're logged in as
    if request.user.id == id:
        raise HTTPException(status_code=400, detail="You cannot delete yourself")

    # You can't delete the last admin user
    if user.role == Role.ADMIN and len(db_user_handler.get_admin_users()) == 1:
        raise HTTPException(
            status_code=400, detail="You cannot delete the last admin user"
        )

    db_user_handler.delete_user(id)

    return {"msg": "User successfully deleted"}
