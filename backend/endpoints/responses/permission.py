"""Response schemas for `/permissions/me`.

`ActionKey` is the canonical, UI-facing action vocabulary (mirrors the v2
`useCan` actions). Exposing it here puts it in the OpenAPI schema so the frontend
generates the enum and can delete its hand-authored `actions.ts` / `role-map.ts`.

The grants returned reflect what the BACKEND actually enforces (the source of
truth), resolved from the user's groups + overrides. All scopes are global in
this phase; per-resource scoping is reserved for later.
"""

from __future__ import annotations

import enum
from typing import Literal

from pydantic import BaseModel

from handler.auth.permissions import ResolvedPermissions
from models.permission import PermAction, PermEntity


class ActionKey(enum.StrEnum):
    # ROMs
    ROM_VIEW = "rom.view"
    ROM_PLAY = "rom.play"
    ROM_DOWNLOAD = "rom.download"
    ROM_UPLOAD = "rom.upload"
    ROM_EDIT = "rom.edit"
    ROM_DELETE = "rom.delete"
    ROM_MATCH = "rom.match"
    ROM_REFRESH = "rom.refresh"
    ROM_FAVORITE = "rom.favorite"
    # Platforms
    PLATFORM_VIEW = "platform.view"
    PLATFORM_CREATE = "platform.create"
    PLATFORM_EDIT = "platform.edit"
    PLATFORM_DELETE = "platform.delete"
    # Collections
    COLLECTION_VIEW = "collection.view"
    COLLECTION_CREATE = "collection.create"
    COLLECTION_EDIT = "collection.edit"
    COLLECTION_DELETE = "collection.delete"
    # Library
    LIBRARY_SCAN = "library.scan"
    # Users
    USER_VIEW = "user.view"
    USER_CREATE = "user.create"
    USER_EDIT = "user.edit"
    USER_DELETE = "user.delete"
    # App-wide "is admin" hatch.
    APP_ADMIN = "app.admin"


# (entity, action) a user holds -> the UI action keys it unlocks. One backend
# grant fans out to several UI actions. Kept faithful to backend enforcement:
# e.g. platform create/delete and rom delete gate on the platform/rom write or
# delete grants the legacy editor already held.
_ENTITY_ACTION_KEYS: dict[tuple[PermEntity, PermAction], tuple[ActionKey, ...]] = {
    (PermEntity.ROMS, PermAction.READ): (
        ActionKey.ROM_VIEW,
        ActionKey.ROM_PLAY,
        ActionKey.ROM_DOWNLOAD,
        ActionKey.ROM_FAVORITE,
    ),
    (PermEntity.ROMS, PermAction.WRITE): (
        ActionKey.ROM_UPLOAD,
        ActionKey.ROM_EDIT,
        ActionKey.ROM_MATCH,
        ActionKey.ROM_REFRESH,
    ),
    (PermEntity.ROMS, PermAction.DELETE): (ActionKey.ROM_DELETE,),
    (PermEntity.PLATFORMS, PermAction.READ): (ActionKey.PLATFORM_VIEW,),
    (PermEntity.PLATFORMS, PermAction.WRITE): (
        ActionKey.PLATFORM_CREATE,
        ActionKey.PLATFORM_EDIT,
        ActionKey.LIBRARY_SCAN,
    ),
    (PermEntity.PLATFORMS, PermAction.DELETE): (ActionKey.PLATFORM_DELETE,),
    (PermEntity.COLLECTIONS, PermAction.READ): (ActionKey.COLLECTION_VIEW,),
    (PermEntity.COLLECTIONS, PermAction.WRITE): (
        ActionKey.COLLECTION_CREATE,
        ActionKey.COLLECTION_EDIT,
    ),
    (PermEntity.COLLECTIONS, PermAction.DELETE): (ActionKey.COLLECTION_DELETE,),
    (PermEntity.USERS, PermAction.READ): (ActionKey.USER_VIEW,),
    (PermEntity.USERS, PermAction.WRITE): (
        ActionKey.USER_CREATE,
        ActionKey.USER_EDIT,
        ActionKey.USER_DELETE,
    ),
}


class PermissionScopeSchema(BaseModel):
    kind: Literal["global", "platform", "collection", "rom"] = "global"
    id: int | None = None


class GrantSchema(BaseModel):
    action: ActionKey
    scope: PermissionScopeSchema


class HiddenEntitiesSchema(BaseModel):
    platforms: list[int]
    roms: list[int]


class PermissionsResponse(BaseModel):
    is_admin: bool
    grants: list[GrantSchema]
    hidden: HiddenEntitiesSchema

    @classmethod
    def from_resolved(cls, perms: ResolvedPermissions) -> PermissionsResponse:
        keys = action_keys_for(perms)
        return cls(
            is_admin=perms.is_admin,
            grants=[
                GrantSchema(action=k, scope=PermissionScopeSchema(kind="global"))
                for k in keys
            ],
            hidden=HiddenEntitiesSchema(
                platforms=sorted(perms.hidden_platform_ids),
                roms=sorted(perms.hidden_rom_ids),
            ),
        )


def action_keys_for(perms: ResolvedPermissions) -> list[ActionKey]:
    """The UI action keys a user can perform, in enum order.

    Admins unlock everything (the frontend also short-circuits on `is_admin`).
    Otherwise each held grant fans out to its UI actions; `owned=True` makes
    own-only grants (e.g. manage own collections) count as "can do this action".
    """
    if perms.is_admin:
        return list(ActionKey)

    keys: set[ActionKey] = set()
    for (entity, action), action_keys in _ENTITY_ACTION_KEYS.items():
        if perms.allows(entity, action, owned=True):
            keys.update(action_keys)
    return [k for k in ActionKey if k in keys]


# --- Admin CRUD schemas -------------------------------------------------------


class GrantSchemaIO(BaseModel):
    """A single (entity, action) grant on a group, with the own-only flag."""

    entity: PermEntity
    action: PermAction
    own_only: bool = False


class PermissionGroupSchema(BaseModel):
    id: int
    name: str
    description: str
    is_default: bool
    is_system: bool
    grants: list[GrantSchemaIO]
    member_count: int

    model_config = {"from_attributes": True}


class PermissionGroupCreate(BaseModel):
    name: str
    description: str = ""
    is_default: bool = False
    grants: list[GrantSchemaIO] = []


class PermissionGroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_default: bool | None = None
    grants: list[GrantSchemaIO] | None = None


class OverrideSchemaIO(BaseModel):
    entity: PermEntity
    action: PermAction
    granted: bool
    own_only: bool = False


class HiddenEntitySchema(BaseModel):
    entity: PermEntity
    entity_id: int


class HiddenEntityCreate(BaseModel):
    entity: PermEntity
    entity_id: int
    # Exactly one principal must be set (validated by the endpoint).
    user_id: int | None = None
    group_id: int | None = None


class UserPermissionsSchema(BaseModel):
    """Admin view of one user's permission assignment."""

    user_id: int
    permission_group_id: int | None
    overrides: list[OverrideSchemaIO]
    hidden: list[HiddenEntitySchema]


class UserPermissionsUpdate(BaseModel):
    # `permission_group_id` is a tri-state: omit to leave unchanged, null to
    # clear (fall back to default group), an id to assign.
    permission_group_id: int | None = None
    set_group: bool = False
    overrides: list[OverrideSchemaIO] | None = None


class PermissionCatalogSchema(BaseModel):
    """The vocabulary the admin UI renders the group/override matrix from."""

    entities: list[PermEntity]
    actions: list[PermAction]
