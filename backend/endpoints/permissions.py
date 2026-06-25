from typing import Annotated

from fastapi import Body, HTTPException, Request, status

from decorators.auth import protected_route
from endpoints.responses.permission import (
    GrantSchemaIO,
    HiddenEntityCreate,
    HiddenEntitySchema,
    OverrideSchemaIO,
    PermissionCatalogSchema,
    PermissionGroupCreate,
    PermissionGroupSchema,
    PermissionGroupUpdate,
    PermissionsResponse,
    UserPermissionsSchema,
    UserPermissionsUpdate,
)
from handler.auth.constants import Scope
from handler.auth.dependencies import assert_admin, get_permissions
from handler.database import db_permission_handler, db_user_handler
from handler.socket_handler import socket_handler
from logger.logger import log
from models.permission import PermAction, PermEntity, PermissionGroup
from utils.router import APIRouter

router = APIRouter(
    prefix="/permissions",
    tags=["permissions"],
)


async def emit_permissions_changed(user_id: int) -> None:
    """Notify clients that `user_id`'s effective permissions changed.

    Broadcast (Redis-backed fan-out); the frontend re-fetches `/permissions/me`
    only when the affected user is the current user. Call this from any path that
    mutates a user's role, group, overrides or hidden entities.
    """
    try:
        await socket_handler.socket_server.emit(
            "permissions:changed", {"user_id": user_id}
        )
    except Exception as e:  # noqa: BLE001
        log.warning(f"Failed to broadcast permissions:changed for user {user_id}: {e}")


@protected_route(router.get, "/me", [Scope.ME_READ])
def get_my_permissions(request: Request) -> PermissionsResponse:
    """Return the caller's effective permissions for the UI to gate on.

    The backend remains the source of truth; this is a UX hint. Includes the
    granted action keys and the platform/rom ids hidden from the caller.
    """
    return PermissionsResponse.from_resolved(get_permissions(request))


# --- Admin: catalog -----------------------------------------------------------


@protected_route(router.get, "/catalog", [Scope.USERS_READ])
def get_permission_catalog(request: Request) -> PermissionCatalogSchema:
    """The entity/action vocabulary the admin UI renders its matrix from."""
    assert_admin(request)
    return PermissionCatalogSchema(entities=list(PermEntity), actions=list(PermAction))


# --- Admin: permission groups -------------------------------------------------


def _group_schema(group: PermissionGroup) -> PermissionGroupSchema:
    return PermissionGroupSchema(
        id=group.id,
        name=group.name,
        description=group.description,
        is_default=group.is_default,
        is_system=group.is_system,
        color=group.color,
        grants=[
            GrantSchemaIO(entity=g.entity, action=g.action, own_only=g.own_only)
            for g in group.grants
        ],
        member_count=len(db_permission_handler.get_group_member_ids(group.id)),
        hidden=[
            HiddenEntitySchema(entity=h.entity, entity_id=h.entity_id)
            for h in db_permission_handler.get_hidden_entities(group_id=group.id)
        ],
    )


@protected_route(router.get, "/groups", [Scope.USERS_READ])
def list_permission_groups(request: Request) -> list[PermissionGroupSchema]:
    """List all permission groups with their grants."""
    assert_admin(request)
    return [_group_schema(g) for g in db_permission_handler.get_groups()]


@protected_route(
    router.post, "/groups", [Scope.USERS_WRITE], status_code=status.HTTP_201_CREATED
)
def create_permission_group(
    request: Request, body: PermissionGroupCreate
) -> PermissionGroupSchema:
    """Create a permission group."""
    assert_admin(request)
    if db_permission_handler.get_group_by_name(body.name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A group with that name already exists",
        )
    group = db_permission_handler.create_group(
        name=body.name,
        description=body.description,
        is_default=body.is_default,
        color=body.color,
        grants=[(g.entity, g.action, g.own_only) for g in body.grants],
    )
    return _group_schema(group)


@protected_route(
    router.put,
    "/groups/{id}",
    [Scope.USERS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def update_permission_group(
    request: Request, id: int, body: PermissionGroupUpdate
) -> PermissionGroupSchema:
    """Update a permission group (name/description/default/grants)."""
    assert_admin(request)
    if db_permission_handler.get_group(id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    updated = db_permission_handler.update_group(
        id,
        name=body.name,
        description=body.description,
        is_default=body.is_default,
        color=body.color,
        grants=(
            [(g.entity, g.action, g.own_only) for g in body.grants]
            if body.grants is not None
            else None
        ),
    )
    # Grant changes alter every member's effective permissions.
    for member_id in db_permission_handler.get_group_member_ids(id):
        await emit_permissions_changed(member_id)
    return _group_schema(updated)  # type: ignore[arg-type]


@protected_route(
    router.delete,
    "/groups/{id}",
    [Scope.USERS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def delete_permission_group(request: Request, id: int) -> None:
    """Delete a permission group. Members fall back to the default group."""
    assert_admin(request)
    group = db_permission_handler.get_group(id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if group.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the default group; set another default first",
        )

    member_ids = db_permission_handler.get_group_member_ids(id)
    db_permission_handler.delete_group(id)
    for member_id in member_ids:
        await emit_permissions_changed(member_id)


# --- Admin: per-user assignment ----------------------------------------------


def _user_permissions(
    user_id: int, permission_group_id: int | None
) -> UserPermissionsSchema:
    overrides = db_permission_handler.get_user_overrides(user_id)
    hidden = db_permission_handler.get_hidden_entities(user_id=user_id)
    return UserPermissionsSchema(
        user_id=user_id,
        permission_group_id=permission_group_id,
        overrides=[
            OverrideSchemaIO(
                entity=o.entity,
                action=o.action,
                granted=o.granted,
                own_only=o.own_only,
            )
            for o in overrides
        ],
        hidden=[
            HiddenEntitySchema(entity=h.entity, entity_id=h.entity_id) for h in hidden
        ],
    )


@protected_route(
    router.get,
    "/users/{user_id}",
    [Scope.USERS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
def get_user_permissions(request: Request, user_id: int) -> UserPermissionsSchema:
    """A user's group membership, per-user overrides and hidden entities."""
    assert_admin(request)
    user = db_user_handler.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return _user_permissions(user_id, user.permission_group_id)


@protected_route(
    router.put,
    "/users/{user_id}",
    [Scope.USERS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def update_user_permissions(
    request: Request, user_id: int, body: UserPermissionsUpdate
) -> UserPermissionsSchema:
    """Assign a user's group and/or replace their per-user overrides."""
    assert_admin(request)
    user = db_user_handler.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    group_id = user.permission_group_id
    if body.set_group:
        group_id = body.permission_group_id
        db_permission_handler.set_user_group(user_id, group_id)
    if body.overrides is not None:
        db_permission_handler.replace_user_overrides(
            user_id,
            [(o.entity, o.action, o.granted, o.own_only) for o in body.overrides],
        )

    await emit_permissions_changed(user_id)
    return _user_permissions(user_id, group_id)


# --- Admin: hidden entities ---------------------------------------------------


@protected_route(router.post, "/hidden", [Scope.USERS_WRITE])
async def add_hidden_entity(
    request: Request, body: HiddenEntityCreate
) -> HiddenEntitySchema:
    """Hide an entity from a user OR a group (exactly one principal)."""
    assert_admin(request)
    if (body.user_id is None) == (body.group_id is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exactly one of user_id or group_id must be set",
        )

    db_permission_handler.add_hidden_entity(
        body.entity, body.entity_id, user_id=body.user_id, group_id=body.group_id
    )
    await _emit_for_principal(body.user_id, body.group_id)
    return HiddenEntitySchema(entity=body.entity, entity_id=body.entity_id)


@protected_route(
    router.delete,
    "/hidden",
    [Scope.USERS_WRITE],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_hidden_entity(
    request: Request,
    entity: Annotated[PermEntity, Body(embed=True)],
    entity_id: Annotated[int, Body(embed=True)],
    user_id: Annotated[int | None, Body(embed=True)] = None,
    group_id: Annotated[int | None, Body(embed=True)] = None,
) -> None:
    """Un-hide an entity for a user OR a group."""
    assert_admin(request)
    if (user_id is None) == (group_id is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exactly one of user_id or group_id must be set",
        )
    db_permission_handler.remove_hidden_entity(
        entity, entity_id, user_id=user_id, group_id=group_id
    )
    await _emit_for_principal(user_id, group_id)


async def _emit_for_principal(user_id: int | None, group_id: int | None) -> None:
    if user_id is not None:
        await emit_permissions_changed(user_id)
    elif group_id is not None:
        for member_id in db_permission_handler.get_group_member_ids(group_id):
            await emit_permissions_changed(member_id)
