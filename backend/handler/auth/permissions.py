"""Per-request permission resolution and the coarse ``oauth_scopes`` projection.

This is the authoritative source the auth layer consults. ``resolve_permissions``
computes a user's effective grants (group ∪ overrides, admin bypass) plus the set
of entity ids hidden from them; ``compute_oauth_scopes`` projects the grants onto
the legacy coarse ``Scope`` vocabulary so the existing scope-based enforcement,
client tokens and OAuth flow keep working unchanged.

Precedence: admin bypass > per-user override > group grant > legacy default.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from config import KIOSK_MODE
from decorators.database import INJECTED_SESSION, begin_session
from handler.auth.constants import FULL_SCOPES, READ_SCOPES, Scope
from handler.auth.permissions_map import (
    grants_to_scopes,
    order_scopes,
)
from handler.auth.rom_visibility import (
    UNRESTRICTED,
    RomVisibilityFilter,
    VisibilityColumns,
)
from models.permission import PermAction, PermEntity
from models.user import Role, User

if TYPE_CHECKING:
    from handler.database.permissions_handler import GroupPolicy


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
    age_limit: int | None = None
    hide_unrated_roms: bool = False
    age_exempt_rom_ids: frozenset[int] = frozenset()

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

    @cached_property
    def rom_visibility(self) -> RomVisibilityFilter:
        if self.is_admin:
            return UNRESTRICTED
        return RomVisibilityFilter(
            hidden_platform_ids=self.hidden_platform_ids,
            hidden_rom_ids=self.hidden_rom_ids,
            age_limit=self.age_limit,
            hide_unrated=self.hide_unrated_roms,
            exempt_rom_ids=self.age_exempt_rom_ids,
        )

    @cached_property
    def can_see_rom(self) -> Callable[[VisibilityColumns], bool]:
        return self.rom_visibility.allows


def _effective_group_id(user: User, *, session: Session) -> int | None:
    """The group a non-admin user follows: their own, else the server default.

    A user with no explicit group inherits the default group's grants, hides
    and age settings alike.
    """

    from handler.database import db_permission_handler

    if user.permission_group_id is not None:
        return user.permission_group_id
    return db_permission_handler.get_default_group_id(session=session)


def _group_policy(group_id: int | None, *, session: Session) -> GroupPolicy | None:
    from handler.database import db_permission_handler

    if group_id is None:
        return None
    return db_permission_handler.get_group_policy(group_id, session=session)


def _resolve_grant_map(
    user: User, group: GroupPolicy | None, *, session: Session
) -> dict[tuple[PermEntity, PermAction], bool]:
    """Effective ``(entity, action) -> own_only`` map for a non-admin user."""

    from handler.database import db_permission_handler

    base: dict[tuple[PermEntity, PermAction], bool] = {}
    if group is not None:
        for entity, action, own_only in group.grants:
            base[(entity, action)] = own_only

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


def resolve_permissions(user: User) -> ResolvedPermissions:
    # Admins bypass everything -- no DB access needed.
    if user.role == Role.ADMIN:
        return ResolvedPermissions(
            is_admin=True,
            user_id=user.id,
            grants=frozenset(),
            hidden_platform_ids=frozenset(),
            hidden_rom_ids=frozenset(),
        )
    return _resolve_non_admin(user)


@begin_session
def _resolve_non_admin(
    user: User,
    *,
    session: Session = INJECTED_SESSION,
) -> ResolvedPermissions:
    from handler.database import db_permission_handler

    group_id = _effective_group_id(user, session=session)
    group = _group_policy(group_id, session=session)
    grant_map = _resolve_grant_map(user, group, session=session)
    grants = frozenset(
        ResolvedGrant(entity, action, own_only)
        for (entity, action), own_only in grant_map.items()
    )
    # Cap the anonymous visitor at the fine layer too, so a mutating route gated
    # only by `assert_can` (no coarse scope) stays blocked for them.
    if KIOSK_MODE and user.is_kiosk_guest:
        grants = frozenset(g for g in grants if g.action == PermAction.READ)

    hidden_platforms = db_permission_handler.get_hidden_entity_ids(
        PermEntity.PLATFORMS, user.id, group_id, session=session
    )
    hidden_roms = db_permission_handler.get_hidden_entity_ids(
        PermEntity.ROMS, user.id, group_id, session=session
    )

    # The user's own age settings replace the group's; NULL inherits.
    age_limit = user.age_limit
    if age_limit is None and group is not None:
        age_limit = group.age_limit
    hide_unrated = user.hide_unrated_roms
    if hide_unrated is None:
        hide_unrated = group.hide_unrated_roms if group is not None else False
    exempt = (
        db_permission_handler.get_age_exempt_rom_ids(user.id, group_id, session=session)
        if age_limit is not None or hide_unrated
        else set()
    )

    return ResolvedPermissions(
        is_admin=False,
        user_id=user.id,
        grants=grants,
        hidden_platform_ids=frozenset(hidden_platforms),
        hidden_rom_ids=frozenset(hidden_roms),
        age_limit=age_limit,
        hide_unrated_roms=hide_unrated,
        age_exempt_rom_ids=frozenset(exempt),
    )


def compute_oauth_scopes(user: User) -> list[Scope]:
    """Project a user's effective grants onto the coarse legacy ``Scope`` set.

    Admins get the full set; the anonymous ``KIOSK_MODE`` visitor is capped to
    read-only (the public-display lockdown).
    """

    # Admins bypass everything -- no DB access needed. Keep the canonical
    # FULL_SCOPES order (same as the non-admin path) to avoid token churn.
    if user.role == Role.ADMIN:
        return order_scopes(FULL_SCOPES)
    return _compute_non_admin_scopes(user)


@begin_session
def _compute_non_admin_scopes(
    user: User,
    *,
    session: Session = INJECTED_SESSION,
) -> list[Scope]:
    group = _group_policy(_effective_group_id(user, session=session), session=session)
    grant_map = _resolve_grant_map(user, group, session=session)
    scopes = set(
        grants_to_scopes(
            (entity, action, own_only)
            for (entity, action), own_only in grant_map.items()
        )
    )
    # Kiosk mode is an anonymous-visitor lockdown, not an account-wide cap: a
    # user someone deliberately logged into keeps the grants they were given.
    if KIOSK_MODE and user.is_kiosk_guest:
        scopes &= set(READ_SCOPES)
    return order_scopes(scopes)
