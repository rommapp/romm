from typing import Annotated

from adapters.services.smb_controller import SmbControllerError, smb_controller
from config import (
    ENABLE_SMB,
    SMB_ADVERTISED_HOST,
    SMB_ADVERTISED_PORT,
    SMB_WORKGROUP,
)
from decorators.auth import protected_route
from fastapi import Body, HTTPException, Query, Request, Response, status
from handler.auth.constants import Scope
from handler.auth.dependencies import assert_admin
from handler.smb_access_handler import _share_name, smb_access_handler
from models.smb import SmbAccessMode, SmbUser
from pydantic import BaseModel, Field, field_validator
from utils.router import APIRouter

from endpoints.responses.smb import (
    SmbLogsSchema,
    SmbPlatformPermissionSchema,
    SmbStatusSchema,
    SmbUserSchema,
    SmbUserSecretSchema,
)

router = APIRouter(prefix="/smb", tags=["smb"])


class SmbPermissionPayload(BaseModel):
    platform_id: int = Field(ge=1)
    access: SmbAccessMode


class SmbUserCreatePayload(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-z][a-z0-9._-]+$")
    permissions: list[SmbPermissionPayload] = Field(min_length=1)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()


class SmbUserUpdatePayload(BaseModel):
    permissions: list[SmbPermissionPayload] = Field(min_length=1)


def _require_enabled() -> None:
    if not ENABLE_SMB:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SMB management is disabled",
        )


def _permissions_schema(user: SmbUser) -> list[SmbPlatformPermissionSchema]:
    return [
        SmbPlatformPermissionSchema(
            platform_id=permission.platform.id,
            platform_name=permission.platform.custom_name or permission.platform.name,
            platform_fs_slug=permission.platform.fs_slug,
            share_name=_share_name(
                permission.platform.id, permission.platform.fs_slug
            ),
            access=permission.access,
        )
        for permission in user.permissions
    ]


def _schema(user: SmbUser) -> SmbUserSchema:
    return SmbUserSchema(
        id=user.id,
        username=user.username,
        permissions=_permissions_schema(user),
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _secret_schema(user: SmbUser, password: str) -> SmbUserSecretSchema:
    return SmbUserSecretSchema(
        id=user.id,
        username=user.username,
        permissions=_permissions_schema(user),
        created_at=user.created_at,
        updated_at=user.updated_at,
        password=password,
    )


def _permissions(payload: list[SmbPermissionPayload]):
    return [(item.platform_id, item.access) for item in payload]


def _controller_error(exc: SmbControllerError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=str(exc),
    )


def _prevent_secret_caching(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def _get_status() -> SmbStatusSchema:
    users = smb_access_handler.list_users()
    if not ENABLE_SMB:
        return SmbStatusSchema(
            enabled=False,
            controller_online=False,
            samba_running=False,
            advertised_host=SMB_ADVERTISED_HOST,
            advertised_port=SMB_ADVERTISED_PORT,
            workgroup=SMB_WORKGROUP,
            user_count=len(users),
        )
    try:
        controller_status = smb_controller.status()
    except SmbControllerError:
        return SmbStatusSchema(
            enabled=True,
            controller_online=False,
            samba_running=False,
            advertised_host=SMB_ADVERTISED_HOST,
            advertised_port=SMB_ADVERTISED_PORT,
            workgroup=SMB_WORKGROUP,
            user_count=len(users),
        )
    return SmbStatusSchema(
        enabled=True,
        controller_online=True,
        samba_running=bool(controller_status.get("samba_running")),
        samba_version=controller_status.get("samba_version"),
        advertised_host=SMB_ADVERTISED_HOST,
        advertised_port=SMB_ADVERTISED_PORT,
        workgroup=str(controller_status.get("workgroup") or SMB_WORKGROUP),
        started_at=controller_status.get("started_at"),
        user_count=len(users),
    )


@protected_route(router.get, "/status", [Scope.USERS_READ])
def get_status(request: Request) -> SmbStatusSchema:
    assert_admin(request)
    return _get_status()


@protected_route(router.post, "/start", [Scope.USERS_WRITE])
def start_service(request: Request) -> SmbStatusSchema:
    assert_admin(request)
    _require_enabled()
    try:
        smb_controller.start()
        smb_access_handler.sync_config()
    except SmbControllerError as exc:
        raise _controller_error(exc) from exc
    return _get_status()


@protected_route(router.post, "/restart", [Scope.USERS_WRITE])
def restart_service(request: Request) -> SmbStatusSchema:
    assert_admin(request)
    _require_enabled()
    try:
        smb_controller.restart()
        smb_access_handler.sync_config()
    except SmbControllerError as exc:
        raise _controller_error(exc) from exc
    return _get_status()


@protected_route(router.get, "/logs", [Scope.USERS_READ])
def get_logs(
    request: Request,
    lines: int = Query(default=200, ge=1, le=500),
) -> SmbLogsSchema:
    assert_admin(request)
    _require_enabled()
    try:
        return SmbLogsSchema(lines=smb_controller.logs(lines))
    except SmbControllerError as exc:
        raise _controller_error(exc) from exc


@protected_route(router.get, "/users", [Scope.USERS_READ])
def list_users(request: Request) -> list[SmbUserSchema]:
    assert_admin(request)
    return [_schema(user) for user in smb_access_handler.list_users()]


@protected_route(
    router.post,
    "/users",
    [Scope.USERS_WRITE],
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    request: Request,
    response: Response,
    payload: Annotated[SmbUserCreatePayload, Body()],
) -> SmbUserSecretSchema:
    assert_admin(request)
    _require_enabled()
    if smb_access_handler.get_user_by_username(payload.username):
        raise HTTPException(status_code=409, detail="SMB username already exists")
    try:
        user, password = smb_access_handler.create_user(
            payload.username, _permissions(payload.permissions)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SmbControllerError as exc:
        raise _controller_error(exc) from exc
    _prevent_secret_caching(response)
    return _secret_schema(user, password)


@protected_route(router.put, "/users/{user_id}", [Scope.USERS_WRITE])
def update_user(
    request: Request,
    user_id: int,
    payload: Annotated[SmbUserUpdatePayload, Body()],
) -> SmbUserSchema:
    assert_admin(request)
    _require_enabled()
    try:
        user = smb_access_handler.update_user(
            user_id, _permissions(payload.permissions)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SmbControllerError as exc:
        raise _controller_error(exc) from exc
    if user is None:
        raise HTTPException(status_code=404, detail="SMB user not found")
    return _schema(user)


@protected_route(router.post, "/users/{user_id}/rotate", [Scope.USERS_WRITE])
def rotate_user(
    request: Request, response: Response, user_id: int
) -> SmbUserSecretSchema:
    assert_admin(request)
    _require_enabled()
    try:
        result = smb_access_handler.rotate_password(user_id)
    except SmbControllerError as exc:
        raise _controller_error(exc) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="SMB user not found")
    user, password = result
    _prevent_secret_caching(response)
    return _secret_schema(user, password)


@protected_route(router.delete, "/users/{user_id}", [Scope.USERS_WRITE])
def delete_user(request: Request, user_id: int) -> None:
    assert_admin(request)
    _require_enabled()
    try:
        deleted = smb_access_handler.delete_user(user_id)
    except SmbControllerError as exc:
        raise _controller_error(exc) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="SMB user not found")


@protected_route(router.post, "/sync", [Scope.USERS_WRITE])
def sync_config(request: Request) -> None:
    assert_admin(request)
    _require_enabled()
    try:
        smb_access_handler.sync_config()
    except SmbControllerError as exc:
        raise _controller_error(exc) from exc
