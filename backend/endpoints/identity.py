import secrets
from typing import Annotated

from config import ROMM_AUTH_ENABLED
from decorators.auth import protected_route
from endpoints.forms.identity import UserForm
from endpoints.responses import MessageResponse
from endpoints.responses.identity import UserSchema
from exceptions.auth_exceptions import AuthCredentialsException, DisabledException
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security.http import HTTPBasic
from handler import authh, dbh, fsresourceh
from handler.redis_handler import cache
from models.user import Role, User

router = APIRouter()


@router.post("/login")
def login(request: Request, credentials=Depends(HTTPBasic())) -> MessageResponse:
    """Session login endpoint

    Args:
        request (Request): Fastapi Request object
        credentials: Defaults to Depends(HTTPBasic()).

    Raises:
        CredentialsException: Invalid credentials
        DisabledException: Auth is disabled

    Returns:
        MessageResponse: Standard message response
    """

    user = authh.authenticate_user(credentials.username, credentials.password)
    if not user:
        raise AuthCredentialsException

    if not user.enabled:
        raise DisabledException

    # Generate unique session key and store in cache
    request.session["session_id"] = secrets.token_hex(16)
    cache.set(f'romm:{request.session["session_id"]}', user.username)  # type: ignore[attr-defined]

    return {"message": "Successfully logged in"}


@router.post("/logout")
def logout(request: Request) -> MessageResponse:
    """Session logout endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        MessageResponse: Standard message response
    """

    # Check if session key already stored in cache
    session_id = request.session.get("session_id")
    if not session_id:
        return {"message": "Already logged out"}

    if not request.user.is_authenticated:
        return {"message": "Already logged out"}

    authh.clear_session(request)

    return {"message": "Successfully logged out"}


@protected_route(router.get, "/users", ["users.read"])
def users(request: Request) -> list[UserSchema]:
    """Get all users endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        list[UserSchema]: All users stored in the RomM's database
    """

    return dbh.get_users()


@protected_route(router.get, "/users/me", ["me.read"])
def current_user(request: Request) -> UserSchema | None:
    """Get current user endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        UserSchema | None: Current user stored in the RomM's database
    """

    return request.user


@protected_route(router.get, "/users/{user_id}", ["users.read"])
def get_user(request: Request, user_id: int) -> UserSchema:
    """Get user endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        UserSchem: User stored in the RomM's database
    """

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
def create_user(
    request: Request, username: str, password: str, role: str
) -> UserSchema:
    """Create user endpoint

    Args:
        request (Request): Fastapi Requests object
        username (str): User username
        password (str): User password
        role (str): RomM Role object represented as string

    Raises:
        HTTPException: ROMM_AUTH_ENABLED is disabled

    Returns:
        UserSchema: Created user info
    """

    if not ROMM_AUTH_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="Cannot create user: ROMM_AUTH_ENABLED is set to False",
        )

    user = User(
        username=username,
        hashed_password=authh.get_password_hash(password),
        role=Role[role.upper()],
    )

    return dbh.add_user(user)


@protected_route(router.patch, "/users/{user_id}", ["users.write"])
def update_user(
    request: Request, user_id: int, form_data: Annotated[UserForm, Depends()]
) -> UserSchema:
    """Update user endpoint

    Args:
        request (Request): Fastapi Requests object
        user_id (int): User internal id
        form_data (Annotated[UserUpdateForm, Depends): Form Data with user updated info

    Raises:
        HTTPException: ROMM_AUTH_ENABLED is disabled
        HTTPException: User is not found in database
        HTTPException: Username already in use by another user

    Returns:
        UserSchema: Updated user info
    """

    if not ROMM_AUTH_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="Cannot update user: ROMM_AUTH_ENABLED is set to False",
        )
    user = dbh.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    cleaned_data = {}

    if form_data.username and form_data.username != user.username:
        existing_user = dbh.get_user_by_username(form_data.username.lower())
        if existing_user:
            raise HTTPException(
                status_code=400, detail="Username already in use by another user"
            )

        cleaned_data["username"] = form_data.username.lower()

    if form_data.password:
        cleaned_data["hashed_password"] = authh.get_password_hash(form_data.password)

    # You can't change your own role
    if form_data.role and request.user.id != user_id:
        cleaned_data["role"] = Role[form_data.role.upper()]  # type: ignore[assignment]

    # You can't disable yourself
    if form_data.enabled is not None and request.user.id != user_id:
        cleaned_data["enabled"] = form_data.enabled  # type: ignore[assignment]

    if form_data.avatar is not None:
        cleaned_data["avatar_path"], avatar_user_path = fsresourceh.build_avatar_path(
            form_data.avatar.filename, form_data.username
        )
        file_location = f"{avatar_user_path}/{form_data.avatar.filename}"
        with open(file_location, "wb+") as file_object:
            file_object.write(form_data.avatar.file.read())

    if cleaned_data:
        dbh.update_user(user_id, cleaned_data)

        # Log out the current user if username or password changed
        creds_updated = cleaned_data.get("username") or cleaned_data.get(
            "hashed_password"
        )
        if request.user.id == user_id and creds_updated:
            authh.clear_session(request)

    return dbh.get_user(user_id)


@protected_route(router.delete, "/users/{user_id}", ["users.write"])
def delete_user(request: Request, user_id: int) -> MessageResponse:
    """Delete user endpoint

    Args:
        request (Request): Fastapi Request object
        user_id (int): User internal id

    Raises:
        HTTPException: ROMM_AUTH_ENABLED is disabled
        HTTPException: User is not found in database
        HTTPException: User deleting itself
        HTTPException: User is the last admin user

    Returns:
        MessageResponse: Standard message response
    """

    if not ROMM_AUTH_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete user: ROMM_AUTH_ENABLED is set to False",
        )

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
