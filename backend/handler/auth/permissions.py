"""Per-request permission resolution and the coarse ``oauth_scopes`` projection.

This is the authoritative source the auth layer consults. ``resolve_permissions``
computes a user's effective grants (group ∪ overrides, admin bypass) plus the set
of entity ids hidden from them; ``compute_oauth_scopes`` projects the grants onto
the legacy coarse ``Scope`` vocabulary so the existing scope-based enforcement,
client tokens and OAuth flow keep working unchanged.

Precedence: admin bypass > per-user override > group grant > legacy default.
"""

from __future__ import annotations

from dataclasses import dataclass

from config import KIOSK_MODE
from decorators.database import begin_session
from handler.auth.constants import FULL_SCOPES, READ_SCOPES, Scope
from handler.auth.permissions_map import (
    grants_to_scopes,
    order_scopes,
)
from models.permission import PermAction, PermEntity
from models.user import Role, User


@dataclass(frozen=True)
class ResolvedGrant:
    entity: PermEntity
    action: PermAction
    own_only: bool


@dataclass(frozen=True)
class ResolvedPermissions:
    is_admin: bool
    user_id: int | None
    grants: frozenset[ResolvedGrant]
    hidden_platform_ids: frozenset[int]
    hidden_rom_ids: frozenset[int]

    def allows(
        self, entity: PermEntity, action: PermAction, *, owned: bool | None = None
    ) -> bool:
        if self.is_admin:
            return True
        for g in self.grants:
            if g.entity != entity or g.action != action:
                continue
            # own_only grants only satisfy a check on an owned resource.
            if g.own_only and owned is not True:
                continue
            return True
        return False

    def can_see_platform(self, platform_id: int) -> bool:
        return self.is_admin or platform_id not in self.hidden_platform_ids

    def can_see_rom(self, rom_id: int, platform_id: int) -> bool:
        if self.is_admin:
            return True
        return (
            platform_id not in self.hidden_platform_ids
            and rom_id not in self.hidden_rom_ids
        )


def _effective_group_id(user: User, *, session) -> int | None:
    """The group a non-admin user follows: their own, else the server default.

    Used by both the grant map and the hidden-entity lookup so a user with no
    explicit group still inherits the default group's grants AND its hides.
    """

    from handler.database import db_permission_handler

    if user.permission_group_id is not None:
        return user.permission_group_id
    default_group = db_permission_handler.get_default_group(session=session)
    return default_group.id if default_group else None


def _resolve_grant_map(
    user: User, *, session
) -> dict[tuple[PermEntity, PermAction], bool]:
    """Effective ``(entity, action) -> own_only`` map for a non-admin user."""

    from handler.database import db_permission_handler

    base: dict[tuple[PermEntity, PermAction], bool] = {}
    group_id = _effective_group_id(user, session=session)
    if group_id is not None:
        for g in db_permission_handler.get_group_grants(group_id, session=session):
            base[(g.entity, g.action)] = g.own_only

    # Per-user overrides win over the group: grant adds, revoke removes.
    # Override identity is (entity, action) only, so a grant override fully
    # replaces the group's own_only for that key rather than merging. Both
    # directions are admin-initiated and the narrowing case fails closed, so
    # this is a granularity limit, not a privilege leak.
    if user.id is not None:
        for ov in db_permission_handler.get_user_overrides(user.id, session=session):
            if ov.granted:
                base[(ov.entity, ov.action)] = ov.own_only
            else:
                base.pop((ov.entity, ov.action), None)

    return base


def resolve_permissions(
    user: User,
    *,
    session=None,  # type: ignore
) -> ResolvedPermissions:
    # Admins bypass everything -- no DB access needed.
    if user.role == Role.ADMIN:
        return ResolvedPermissions(
            is_admin=True,
            user_id=user.id,
            grants=frozenset(),
            hidden_platform_ids=frozenset(),
            hidden_rom_ids=frozenset(),
        )
    return _resolve_non_admin(user, session=session)


@begin_session
def _resolve_non_admin(
    user: User,
    *,
    session=None,  # type: ignore
) -> ResolvedPermissions:
    from handler.database import db_permission_handler

    grant_map = _resolve_grant_map(user, session=session)
    grants = frozenset(
        ResolvedGrant(entity, action, own_only)
        for (entity, action), own_only in grant_map.items()
    )
    # Kiosk mode locks every non-admin to read-only at the fine layer too, so a
    # mutating route gated only by `assert_can` (no coarse scope) stays blocked.
    if KIOSK_MODE:
        grants = frozenset(g for g in grants if g.action == PermAction.READ)

    # Resolve the effective group (own or default) so hides assigned to the
    # default group apply to group-less users too, not just their grants.
    group_id = _effective_group_id(user, session=session)
    hidden_platforms = db_permission_handler.get_hidden_entity_ids(
        PermEntity.PLATFORMS, user.id, group_id, session=session
    )
    hidden_roms = db_permission_handler.get_hidden_entity_ids(
        PermEntity.ROMS, user.id, group_id, session=session
    )

    return ResolvedPermissions(
        is_admin=False,
        user_id=user.id,
        grants=grants,
        hidden_platform_ids=frozenset(hidden_platforms),
        hidden_rom_ids=frozenset(hidden_roms),
    )


def compute_oauth_scopes(
    user: User,
    *,
    session=None,  # type: ignore
) -> list[Scope]:
    """Project a user's effective grants onto the coarse legacy ``Scope`` set.

    Admins get the full set; ``KIOSK_MODE`` caps every non-admin user to
    read-only (the public-display lockdown).
    """

    # Admins bypass everything -- no DB access needed. Keep the canonical
    # FULL_SCOPES order (same as the non-admin path) to avoid token churn.
    if user.role == Role.ADMIN:
        return order_scopes(FULL_SCOPES)
    return _compute_non_admin_scopes(user, session=session)


@begin_session
def _compute_non_admin_scopes(
    user: User,
    *,
    session=None,  # type: ignore
) -> list[Scope]:
    grant_map = _resolve_grant_map(user, session=session)
    scopes = set(
        grants_to_scopes(
            (entity, action, own_only)
            for (entity, action), own_only in grant_map.items()
        )
    )
    # Only non-admins reach here (admins short-circuit above), so kiosk mode
    # locks all of them down to read-only.
    if KIOSK_MODE:
        scopes &= set(READ_SCOPES)
    return order_scopes(scopes)
