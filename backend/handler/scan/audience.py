"""Who a scan's socket events reach: users who may follow a scan, and of them,
for a ROM or platform event, only those who can see it."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Final

from handler.auth.constants import Scope
from handler.auth.permissions import compute_oauth_scopes_by_user
from handler.auth.rom_visibility import RomVisibilityFilter, VisibilityColumns
from handler.database import db_permission_handler, db_user_handler
from handler.redis_handler import sync_cache
from handler.socket_handler import user_room
from models.user import User

# Joined on connect by every socket whose user may follow a scan.
SCAN_ROOM: Final = "scan"

# Opening the scan view needs the first, starting a scan the second.
SCAN_FOLLOWER_SCOPES: Final = frozenset({Scope.PLATFORMS_WRITE, Scope.TASKS_RUN})


def follows_scans(user: User) -> bool:
    return not SCAN_FOLLOWER_SCOPES.isdisjoint(user.oauth_scopes)


@dataclass(frozen=True)
class ScanAudience:
    """The followers' `user_room` rooms, grouped by what they can see, so a
    per-ROM check costs one test per distinct visibility rather than per user."""

    rooms_by_visibility: Mapping[RomVisibilityFilter, tuple[str, ...]]

    def rom_rooms(self, rom: VisibilityColumns) -> list[str]:
        return [
            room
            for visibility, rooms in self.rooms_by_visibility.items()
            if visibility.allows(rom)
            for room in rooms
        ]

    def platform_rooms(self, platform_id: int) -> list[str]:
        return [
            room
            for visibility, rooms in self.rooms_by_visibility.items()
            if platform_id not in visibility.hidden_platform_ids
            for room in rooms
        ]


def resolve_scan_audience() -> ScanAudience:
    users = db_user_handler.get_enabled_principals()
    scopes = compute_oauth_scopes_by_user(users)
    follower_ids = [
        user_id
        for user_id, user_scopes in scopes.items()
        if not SCAN_FOLLOWER_SCOPES.isdisjoint(user_scopes)
    ]
    rooms: defaultdict[RomVisibilityFilter, list[str]] = defaultdict(list)
    if follower_ids:
        visibilities = db_permission_handler.get_user_visibilities(follower_ids)
        for user_id, visibility in visibilities.items():
            rooms[visibility].append(user_room(user_id))
    return ScanAudience({vis: tuple(r) for vis, r in rooms.items()})


# Bumped on every permission change, so a running scan knows its audience is stale.
PERMISSIONS_GENERATION_KEY: Final = "permissions:generation"


def bump_permissions_generation() -> None:
    sync_cache.incr(PERMISSIONS_GENERATION_KEY)


def _permissions_generation() -> bytes | str | None:
    return sync_cache.get(PERMISSIONS_GENERATION_KEY)


@dataclass
class _ScanAudienceState:
    audience: ScanAudience
    generation: bytes | str | None


# Mutable, so a refresh made inside one of the scan's tasks reaches the others.
_scan_audience: ContextVar[_ScanAudienceState | None] = ContextVar(
    "scan_audience", default=None
)


def begin_scan_audience() -> None:
    """Resolve the audience for the scan running in this context."""
    generation = _permissions_generation()
    _scan_audience.set(_ScanAudienceState(resolve_scan_audience(), generation))


def current_scan_audience() -> ScanAudience:
    """The running scan's audience, resolved again after a permission change."""
    state = _scan_audience.get()
    if state is None:
        raise RuntimeError("No scan audience: begin_scan_audience() was not called")
    generation = _permissions_generation()
    if generation != state.generation:
        state.audience = resolve_scan_audience()
        state.generation = generation
    return state.audience
