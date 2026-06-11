"""Socket.IO events for real-time user game activity.

Handles:
- activity:start     - client reports starting a game (emits activity:update)
- activity:heartbeat - client refreshes TTL while playing (emits activity:update)
- activity:stop      - client reports stopping (emits activity:clear)
- disconnect         - safety net: clears any activity registered for the socket

All events broadcast to every connected client on the main `/ws` namespace.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TypedDict

from endpoints.responses.activity import ActivityClearSchema
from handler.activity_handler import ActivityEntry, activity_handler
from handler.database import db_rom_handler, db_user_handler
from handler.socket_handler import socket_handler
from logger.logger import log


class ActivityEventPayload(TypedDict, total=False):
    rom_id: int
    user_id: int
    device_id: str


def _empty_string(value: object) -> str:
    if value is None:
        return ""
    return str(value)


async def _store_session(sid: str, user_id: int, device_id: str) -> None:
    """Remember the user/device associated with a socket for disconnect cleanup."""
    try:
        existing = await socket_handler.socket_server.get_session(sid) or {}
    except KeyError:
        existing = {}
    existing["activity_user_id"] = user_id
    existing["activity_device_id"] = device_id
    await socket_handler.socket_server.save_session(sid, existing)


async def _build_entry(
    *, user_id: int, device_id: str, rom_id: int, preserve_started_at: bool
) -> ActivityEntry | None:
    """Look up DB info and assemble an ActivityEntry. Returns None if invalid."""
    user = db_user_handler.get_user(user_id)
    if user is None:
        log.debug(f"activity: unknown user_id {user_id}")
        return None

    rom = db_rom_handler.get_rom(rom_id)
    if rom is None:
        log.debug(f"activity: unknown rom_id {rom_id}")
        return None

    platform = rom.platform
    started_at = datetime.now(timezone.utc).isoformat()

    if preserve_started_at:
        existing = await activity_handler.get_active(user_id, device_id)
        if existing:
            started_at = existing["started_at"]

    # Infer device_type: web is the default for browser-emitted events.
    device_type = "web"
    if device_id != "web":
        # The browser may pass its device_id (a UUID) - we still treat it as "web"
        # because Socket.IO events are only emitted from browser clients.
        device_type = "web"

    return ActivityEntry(
        user_id=user.id,
        username=user.username,
        avatar_path=_empty_string(user.avatar_path),
        rom_id=rom.id,
        rom_name=rom.name or rom.fs_name,
        rom_cover_path=_empty_string(rom.path_cover_s),
        platform_slug=_empty_string(platform.slug) if platform else "",
        platform_name=_empty_string(
            (platform.custom_name or platform.name) if platform else ""
        ),
        device_id=device_id,
        device_type=device_type,
        started_at=started_at,
    )


def _extract_payload(data: object) -> tuple[int | None, str | None, int | None]:
    """Return ``(user_id, device_id, rom_id)`` parsed from an event payload."""
    if not isinstance(data, dict):
        return None, None, None
    try:
        user_id = int(data.get("user_id")) if data.get("user_id") is not None else None
    except (TypeError, ValueError):
        user_id = None
    device_id = data.get("device_id")
    if not isinstance(device_id, str) or not device_id:
        device_id = None
    try:
        rom_id = int(data.get("rom_id")) if data.get("rom_id") is not None else None
    except (TypeError, ValueError):
        rom_id = None
    return user_id, device_id, rom_id


@socket_handler.socket_server.on("activity:start")  # type: ignore
async def activity_start(sid: str, data: ActivityEventPayload) -> None:
    user_id, device_id, rom_id = _extract_payload(data)
    if user_id is None or device_id is None or rom_id is None:
        log.debug(f"activity:start ignored (invalid payload): {data}")
        return

    entry = await _build_entry(
        user_id=user_id,
        device_id=device_id,
        rom_id=rom_id,
        preserve_started_at=False,
    )
    if entry is None:
        return

    await activity_handler.set_active(entry)
    await _store_session(sid, user_id, device_id)
    await socket_handler.socket_server.emit("activity:update", dict(entry))


@socket_handler.socket_server.on("activity:heartbeat")  # type: ignore
async def activity_heartbeat(sid: str, data: ActivityEventPayload) -> None:
    user_id, device_id, rom_id = _extract_payload(data)
    if user_id is None or device_id is None or rom_id is None:
        return

    entry = await _build_entry(
        user_id=user_id,
        device_id=device_id,
        rom_id=rom_id,
        preserve_started_at=True,
    )
    if entry is None:
        return

    await activity_handler.set_active(entry)
    await _store_session(sid, user_id, device_id)
    await socket_handler.socket_server.emit("activity:update", dict(entry))


@socket_handler.socket_server.on("activity:stop")  # type: ignore
async def activity_stop(sid: str, data: ActivityEventPayload | None = None) -> None:
    user_id: int | None = None
    device_id: str | None = None

    if data:
        user_id, device_id, _ = _extract_payload(data)

    # Fall back to the stored session if the payload is missing fields.
    if user_id is None or device_id is None:
        try:
            session = await socket_handler.socket_server.get_session(sid) or {}
        except KeyError:
            session = {}
        user_id = user_id if user_id is not None else session.get("activity_user_id")
        device_id = device_id if device_id else session.get("activity_device_id")

    if user_id is None or not device_id:
        return

    rom_id = await activity_handler.clear_active(int(user_id), device_id)
    if rom_id is None:
        return

    await socket_handler.socket_server.emit(
        "activity:clear",
        ActivityClearSchema(
            user_id=int(user_id), device_id=device_id, rom_id=rom_id
        ).model_dump(),
    )


@socket_handler.socket_server.on("disconnect")  # type: ignore
async def activity_on_disconnect(sid: str) -> None:
    """Safety net: clear any activity tied to a disconnecting socket."""
    try:
        session = await socket_handler.socket_server.get_session(sid) or {}
    except KeyError:
        return

    user_id = session.get("activity_user_id")
    device_id = session.get("activity_device_id")
    if user_id is None or not device_id:
        return

    rom_id = await activity_handler.clear_active(int(user_id), device_id)
    if rom_id is None:
        return

    await socket_handler.socket_server.emit(
        "activity:clear",
        ActivityClearSchema(
            user_id=int(user_id), device_id=device_id, rom_id=rom_id
        ).model_dump(),
    )
