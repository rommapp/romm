from typing import Annotated, Any, cast

from fastapi import Body, Form, HTTPException
from fastapi import Path as PathVar
from fastapi import Request, status

from decorators.auth import protected_route
from endpoints.forms.identity import UserForm
from endpoints.responses.identity import InviteLinkSchema, UserSchema
from handler.auth import auth_handler
from handler.auth.constants import Scope
from handler.database import db_user_handler
from handler.filesystem import fs_asset_handler
from handler.metadata import meta_ra_handler
from handler.metadata.ra_handler import RAUserProgression
from logger.logger import log
from models.user import Role, User
from utils.router import APIRouter
from utils.validation import (
    ValidationError,
    validate_email,
    validate_password,
    validate_username,
)

router = APIRouter(
    prefix="/users",
    tags=["users"],
)


@protected_route(
    router.post,
    "",
    [],
    status_code=status.HTTP_201_CREATED,
)
def add_user(
    request: Request,
    username: str = Body(..., embed=True),
    email: str = Body(..., embed=True),
    password: str = Body(..., embed=True),
    role: str = Body(..., embed=True),
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

    try:
        validate_username(username)
        validate_password(password)
        validate_email(email)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc

    if db_user_handler.get_user_by_username(username):
        msg = f"Username {username} already exists"
        log.error(msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    if email and db_user_handler.get_user_by_email(email):
        msg = f"User with email {email} already exists"
        log.error(msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    user = User(
        username=username.lower(),
        hashed_password=auth_handler.get_password_hash(password),
        email=email.lower() or None,
        role=Role[role.upper()],
    )

    return UserSchema.model_validate(db_user_handler.add_user(user))


@protected_route(
    router.post,
    "/invite-link",
    [],
    status_code=status.HTTP_201_CREATED,
)
def create_invite_link(request: Request, role: str) -> InviteLinkSchema:
    """Create an invite link for a user.

    Args:
        request (Request): FastAPI Request object
        role (str): The role of the user

    Returns:
        InviteLinkSchema: Invite link
    """

    if (
        Scope.USERS_WRITE not in request.auth.scopes
        and len(db_user_handler.get_admin_users()) > 0
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    if role not in [r.value for r in Role]:
        msg = f"Role {role} is not valid"
        log.error(msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    token = auth_handler.generate_invite_link_token(request.user, role=role)
    return InviteLinkSchema.model_validate({"token": token})


@router.post("/register", status_code=status.HTTP_201_CREATED)
def create_user_from_invite(
    username: str = Body(..., embed=True),
    email: str = Body(..., embed=True),
    password: str = Body(..., embed=True),
    token: str = Body(..., embed=True),
) -> UserSchema:
    """Create user endpoint with invite link

    Args:
        username (str): User username
        email (str): User email
        password (str): User password
        token (str): Invite link token

    Returns:
        UserSchema: Newly created user
    """

    try:
        validate_username(username)
        validate_password(password)
        validate_email(email)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc

    if db_user_handler.get_user_by_username(username):
        msg = f"Username {username} already exists"
        log.error(msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    if email and db_user_handler.get_user_by_email(email):
        msg = f"User with email {email} already exists"
        log.error(msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    role = auth_handler.consume_invite_link_token(token)
    user = User(
        username=username.lower(),
        hashed_password=auth_handler.get_password_hash(password),
        email=email.lower() or None,
        role=Role[role.upper()],
    )

    created_user = db_user_handler.add_user(user)

    return UserSchema.model_validate(created_user)


@protected_route(router.get, "", [Scope.USERS_READ])
def get_users(request: Request) -> list[UserSchema]:
    """Get all users endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        list[UserSchema]: All users stored in the RomM's database
    """

    return [UserSchema.model_validate(u) for u in db_user_handler.get_users()]


@protected_route(router.get, "/me", [Scope.ME_READ])
def get_current_user(request: Request) -> UserSchema | None:
    """Get current user endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        UserSchema | None: Current user
    """

    return request.user


@protected_route(router.get, "/{id}", [Scope.USERS_READ])
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

    return UserSchema.model_validate(user)


@protected_route(router.put, "/{id}", [Scope.ME_WRITE])
async def update_user(
    request: Request, id: int, form_data: Annotated[UserForm, Form()]
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

    cleaned_data: dict[str, Any] = {}

    if form_data.username and form_data.username != db_user.username:
        try:
            validate_username(form_data.username)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=exc.message,
            ) from exc

        if db_user_handler.get_user_by_username(form_data.username):
            msg = f"Username {form_data.username} already exists"
            log.error(msg)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=msg,
            )

        cleaned_data["username"] = form_data.username.lower()

    if form_data.password:
        try:
            validate_password(form_data.password)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=exc.message,
            ) from exc
        cleaned_data["hashed_password"] = auth_handler.get_password_hash(
            form_data.password
        )

    if form_data.email is not None and form_data.email != db_user.email:
        try:
            validate_email(form_data.email)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=exc.message,
            ) from exc

        if form_data.email and db_user_handler.get_user_by_email(form_data.email):
            msg = f"User with email {form_data.email} already exists"
            log.error(msg)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=msg,
            )

        cleaned_data["email"] = form_data.email.lower() or None

    # You can't change your own role
    if form_data.role and request.user.id != id:
        cleaned_data["role"] = Role[form_data.role.upper()]  # type: ignore[assignment]

    # You can't disable yourself
    if form_data.enabled is not None and request.user.id != id:
        cleaned_data["enabled"] = form_data.enabled  # type: ignore[assignment]

    if form_data.ra_username:
        cleaned_data["ra_username"] = form_data.ra_username  # type: ignore[assignment]

    if form_data.avatar is not None and form_data.avatar.filename is not None:
        user_avatar_path = fs_asset_handler.build_avatar_path(user=db_user)
        file_extension = form_data.avatar.filename.split(".")[-1]
        file_name = f"avatar.{file_extension}"

        await fs_asset_handler.write_file(
            file=form_data.avatar.file, path=user_avatar_path, filename=file_name
        )
        file_location = f"{user_avatar_path}/{file_name}"
        cleaned_data["avatar_path"] = file_location

    if cleaned_data:
        db_user_handler.update_user(id, cleaned_data)

        # Log out the current user if username or password changed
        creds_updated = cleaned_data.get("username") or cleaned_data.get(
            "hashed_password"
        )
        if request.user.id == id and creds_updated:
            request.session.clear()

    db_user = db_user_handler.get_user(id)
    if not db_user:
        msg = f"Username with id {id} not found"
        log.error(msg)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)

    return UserSchema.model_validate(db_user)


@protected_route(
    router.delete,
    "/{id}",
    [Scope.USERS_WRITE],
    responses={
        status.HTTP_400_BAD_REQUEST: {},
        status.HTTP_404_NOT_FOUND: {},
    },
)
async def delete_user(
    request: Request,
    id: Annotated[int, PathVar(description="User internal id.", ge=1)],
) -> None:
    """Delete a user by ID.

    Raises:
        HTTPException: User is not found in database
        HTTPException: User deleting itself
        HTTPException: User is the last admin user
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

    # Remove the user's folder
    user_avatar_path = fs_asset_handler.build_avatar_path(user=user)
    try:
        await fs_asset_handler.remove_directory(user_avatar_path)
    except FileNotFoundError:
        log.warning(f"Couldn't find avatar directory to delete for {user.username}")


@protected_route(
    router.post,
    "/{id}/ra/refresh",
    [Scope.ME_WRITE],
    status_code=status.HTTP_200_OK,
    summary="Refresh RetroAchievements",
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def refresh_retro_achievements(
    request: Request,
    id: Annotated[int, PathVar(description="User internal id.", ge=1)],
    incremental: Annotated[
        bool,
        Body(
            description="Whether to only retrieve RetroAchievements progression incrementally.",
            embed=True,
        ),
    ] = False,
) -> None:
    """Refresh RetroAchievements progression data for a user."""
    user = db_user_handler.get_user(id)
    if not user or not user.ra_username:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not have a RetroAchievements username set",
        )

    user_progression = await meta_ra_handler.get_user_progression(
        user.ra_username,
        current_progression=(
            cast(RAUserProgression | None, user.ra_progression) if incremental else None
        ),
    )
    db_user_handler.update_user(
        id,
        {
            "ra_progression": user_progression,
        },
    )
    return None
