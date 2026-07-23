"""Pure mapping between the granular permission model and legacy OAuth scopes.

Intentionally free of SQLAlchemy / FastAPI imports so it can be reused by both
the runtime ``oauth_scopes`` projection (added in a later PR) and the unit tests
that prove the migration backfill preserves every user's access.

The grant matrices below are the single source of truth for "what a legacy
viewer/editor could do". ``grants_to_scopes`` projects a resolved grant set back
onto the coarse ``Scope`` vocabulary. On day one the round-trip

    role -> legacy grants -> projected scopes

must equal the user's pre-migration ``oauth_scopes`` exactly (verified by
``tests/handler/auth/test_permissions_parity.py``). The Alembic migration that
seeds the legacy groups inlines the SAME matrix as frozen literals; a test keeps
the two in lockstep.
"""

from __future__ import annotations

from collections.abc import Iterable

from handler.auth.constants import FULL_SCOPES, Scope
from models.permission import PermAction, PermEntity

# (entity, action, own_only)
Grant = tuple[PermEntity, PermAction, bool]

# Canonical scope ordering == the legacy READ -> WRITE -> EDIT -> FULL order
# (each is a prefix of FULL_SCOPES). Ordering projected scopes this way
# reproduces the exact list the old role-based `oauth_scopes` returned.
_SCOPE_ORDER: dict[Scope, int] = {s: i for i, s in enumerate(FULL_SCOPES)}


def order_scopes(scopes: Iterable[Scope]) -> list[Scope]:
    return sorted(scopes, key=lambda s: _SCOPE_ORDER[s])


# Scopes granted unconditionally to any authenticated non-admin "user"
# (self-service): own profile + own per-rom data (play status, notes, ratings).
# These are never gated behind a group -- losing them would, e.g., stop a user
# saving their own game progress.
ALWAYS_ON_SCOPES: frozenset[Scope] = frozenset(
    {
        Scope.ME_READ,
        Scope.ME_WRITE,
        Scope.ROMS_USER_READ,
        Scope.ROMS_USER_WRITE,
    }
)

# (entity, action) -> coarse scopes it projects to. DELETE projects to nothing:
# there is no delete scope today (deletes gate on the matching *_WRITE scope),
# so delete granularity lives only in the new fine-grained layer.
_GRANT_SCOPES: dict[tuple[PermEntity, PermAction], frozenset[Scope]] = {
    (PermEntity.ROMS, PermAction.READ): frozenset({Scope.ROMS_READ}),
    (PermEntity.ROMS, PermAction.WRITE): frozenset({Scope.ROMS_WRITE}),
    (PermEntity.PLATFORMS, PermAction.READ): frozenset({Scope.PLATFORMS_READ}),
    (PermEntity.PLATFORMS, PermAction.WRITE): frozenset({Scope.PLATFORMS_WRITE}),
    (PermEntity.FIRMWARE, PermAction.READ): frozenset({Scope.FIRMWARE_READ}),
    (PermEntity.FIRMWARE, PermAction.WRITE): frozenset({Scope.FIRMWARE_WRITE}),
    (PermEntity.COLLECTIONS, PermAction.READ): frozenset({Scope.COLLECTIONS_READ}),
    (PermEntity.COLLECTIONS, PermAction.WRITE): frozenset({Scope.COLLECTIONS_WRITE}),
    (PermEntity.PLAYLISTS, PermAction.READ): frozenset({Scope.PLAYLISTS_READ}),
    (PermEntity.PLAYLISTS, PermAction.WRITE): frozenset({Scope.PLAYLISTS_WRITE}),
    (PermEntity.ASSETS, PermAction.READ): frozenset({Scope.ASSETS_READ}),
    (PermEntity.ASSETS, PermAction.WRITE): frozenset({Scope.ASSETS_WRITE}),
    (PermEntity.DEVICES, PermAction.READ): frozenset({Scope.DEVICES_READ}),
    (PermEntity.DEVICES, PermAction.WRITE): frozenset({Scope.DEVICES_WRITE}),
    (PermEntity.USERS, PermAction.READ): frozenset({Scope.USERS_READ}),
    (PermEntity.USERS, PermAction.WRITE): frozenset({Scope.USERS_WRITE}),
    (PermEntity.TASKS, PermAction.WRITE): frozenset({Scope.TASKS_RUN}),
    (PermEntity.LOGS, PermAction.READ): frozenset({Scope.LOGS_READ}),
}

# --- Legacy group matrices ----------------------------------------------------
# "Viewer (legacy)" == today's non-kiosk default user (WRITE_SCOPES): read the
# library; create/modify/delete only OWN collections/assets/devices.
LEGACY_VIEWER_GRANTS: tuple[Grant, ...] = (
    (PermEntity.ROMS, PermAction.READ, False),
    (PermEntity.PLATFORMS, PermAction.READ, False),
    (PermEntity.FIRMWARE, PermAction.READ, False),
    (PermEntity.COLLECTIONS, PermAction.READ, False),
    (PermEntity.COLLECTIONS, PermAction.WRITE, True),
    (PermEntity.COLLECTIONS, PermAction.DELETE, True),
    (PermEntity.PLAYLISTS, PermAction.READ, False),
    (PermEntity.PLAYLISTS, PermAction.WRITE, True),
    (PermEntity.PLAYLISTS, PermAction.DELETE, True),
    (PermEntity.ASSETS, PermAction.READ, False),
    (PermEntity.ASSETS, PermAction.WRITE, True),
    (PermEntity.ASSETS, PermAction.DELETE, True),
    (PermEntity.DEVICES, PermAction.READ, True),
    (PermEntity.DEVICES, PermAction.WRITE, True),
    (PermEntity.DEVICES, PermAction.DELETE, True),
)

# "Editor (legacy)" == EDIT_SCOPES: viewer + library-wide write AND delete of
# roms/platforms/firmware. Delete is True here because today's delete endpoints
# gate on *_WRITE -- editors can already delete, so preserving that is required
# to avoid silently revoking access on upgrade.
_LEGACY_EDITOR_EXTRA: tuple[Grant, ...] = (
    (PermEntity.ROMS, PermAction.WRITE, False),
    (PermEntity.ROMS, PermAction.DELETE, False),
    (PermEntity.PLATFORMS, PermAction.WRITE, False),
    (PermEntity.PLATFORMS, PermAction.DELETE, False),
    (PermEntity.FIRMWARE, PermAction.WRITE, False),
    (PermEntity.FIRMWARE, PermAction.DELETE, False),
)

LEGACY_EDITOR_GRANTS: tuple[Grant, ...] = LEGACY_VIEWER_GRANTS + _LEGACY_EDITOR_EXTRA


def grants_to_scopes(grants: Iterable[Grant], *, is_admin: bool = False) -> list[Scope]:
    """Project a resolved grant set onto the coarse legacy ``Scope`` vocabulary.

    Admins always get the full set. For everyone else, the self-service
    ``ALWAYS_ON_SCOPES`` are unioned with the scopes implied by each grant.
    Returned in canonical legacy READ -> WRITE -> EDIT -> FULL order.
    """

    if is_admin:
        return list(FULL_SCOPES)

    out: set[Scope] = set(ALWAYS_ON_SCOPES)
    for entity, action, _own_only in grants:
        out |= _GRANT_SCOPES.get((entity, action), frozenset())
    return order_scopes(out)
