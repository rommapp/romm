"""Who a scan's socket events reach: users who may follow a scan, and of them,
for a ROM or platform event, only those who can see it."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Final

import socketio

from handler.auth.constants import Scope
from handler.auth.rom_visibility import RomVisibilityFilter, VisibilityColumns
from handler.database import db_permission_handler, db_user_handler
from models.user import User

# Joined on connect by every socket whose user may follow a scan.
SCAN_ROOM: Final = "scan"

# Opening the scan view needs the first, starting a scan the second.
SCAN_FOLLOWER_SCOPES: Final = frozenset({Scope.PLATFORMS_WRITE, Scope.TASKS_RUN})


def follows_scans(user: User) -> bool:
    return not SCAN_FOLLOWER_SCOPES.isdisjoint(user.oauth_scopes)


@dataclass(frozen=True)
class ScanAudience:
    """The followers' `user:{id}` rooms, grouped by what they can see, so a
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
    follower_ids = [
        user.id
        for user in db_user_handler.get_users()
        if user.enabled and follows_scans(user)
    ]
    rooms: defaultdict[RomVisibilityFilter, list[str]] = defaultdict(list)
    if follower_ids:
        visibilities = db_permission_handler.get_user_visibilities(follower_ids)
        for user_id, visibility in visibilities.items():
            rooms[visibility].append(f"user:{user_id}")
    return ScanAudience({vis: tuple(r) for vis, r in rooms.items()})


_scan_audience: ContextVar[ScanAudience | None] = ContextVar(
    "scan_audience", default=None
)


def begin_scan_audience() -> None:
    """Resolve the audience once for the scan running in this context."""
    _scan_audience.set(resolve_scan_audience())


def current_scan_audience() -> ScanAudience:
    """The running scan's audience, resolved afresh outside of one."""
    return _scan_audience.get() or resolve_scan_audience()


async def emit_to_rooms(
    socket_manager: socketio.AsyncRedisManager,
    event: str,
    payload: Any,
    rooms: list[str],
) -> None:
    # An empty `to` would broadcast to every socket.
    if rooms:
        await socket_manager.emit(event, payload, to=rooms)
