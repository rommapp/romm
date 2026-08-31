"""Socket.IO events for real-time user game activity.

Handles:
- activity:start     - client reports starting a game (emits activity:update)
- activity:heartbeat - client refreshes TTL while playing (emits activity:update)
- activity:stop      - client reports stopping (emits activity:clear)
- disconnect         - safety net: clears any activity registered for the socket

The acting user is never taken from the client payload — it is resolved from
the authenticated socket session (stored on connect, see ``endpoints.sockets``)
so a client cannot broadcast a "now playing" session on behalf of another user.
Only ``rom_id`` / ``device_id`` come from the client.

All events broadcast to every connected client on the main `/ws` namespace.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from handler.activity_handler import activity_handler
from handler.database import db_user_handler
from handler.socket_handler import socket_handler
from logger.logger import log

if TYPE_CHECKING:
    from models.user import User

# Socket-session key holding the authenticated user id, written by the connect
# handler. Identity for every activity event is derived from this, not payload.
AUTH_USER_SESSION_KEY = "activity_auth_user_id"


class ActivityEventPayload(TypedDict, total=False):
    rom_id: int
    device_id: str


async def _session(sid: str) -> dict[str, Any]:
    try:
        return await socket_handler.socket_server.get_session(sid) or {}
    except KeyError:
        return {}


async def store_authenticated_user(sid: str, user_id: int) -> None:
    """Record the authenticated user for a socket so activity events trust it.

    Called from the connect handler once the session has been resolved. Without
    this, activity events have no identity to act on and are ignored.
    """
    existing = await _session(sid)
    existing[AUTH_USER_SESSION_KEY] = user_id
    await socket_handler.socket_server.save_session(sid, existing)


async def _authenticated_user_id(sid: str) -> int | None:
    """Return the user id resolved at connect time, or ``None`` if unauthenticated."""
    user_id = (await _session(sid)).get(AUTH_USER_SESSION_KEY)
    return int(user_id) if user_id is not None else None


async def get_authenticated_user(sid: str) -> User | None:
    """Return the ``User`` resolved for this socket at connect time, or ``None``.

    Identity comes from the server-resolved session stored on connect, never
    from the client, so socket event handlers can enforce authorization.
    """
    user_id = await _authenticated_user_id(sid)
    if user_id is None:
        return None
    return db_user_handler.get_user(user_id)


async def _store_session(sid: str, user_id: int, device_id: str) -> None:
    """Remember the user/device associated with a socket for disconnect cleanup."""
    existing = await _session(sid)
    existing["activity_user_id"] = user_id
    existing["activity_device_id"] = device_id
    await socket_handler.socket_server.save_session(sid, existing)


def _extract_payload(data: object) -> tuple[str | None, int | None]:
    """Return ``(device_id, rom_id)`` parsed from an event payload.

    ``user_id`` is deliberately not read from the client — identity comes from
    the authenticated socket session, never the payload.
    """
    if not isinstance(data, dict):
        return None, None
    device_id = data.get("device_id")
    if not isinstance(device_id, str) or not device_id:
        device_id = None
    try:
        data_rom_id = data.get("rom_id")
        rom_id = int(data_rom_id) if data_rom_id else None
    except (TypeError, ValueError):
        rom_id = None
    return device_id, rom_id


@socket_handler.socket_server.on("activity:start")  # type: ignore
async def activity_start(sid: str, data: ActivityEventPayload) -> None:
    user_id = await _authenticated_user_id(sid)
    device_id, rom_id = _extract_payload(data)
    if user_id is None or device_id is None or rom_id is None:
        log.debug(f"activity:start ignored (unauthenticated or invalid): {data}")
        return

    entry = await activity_handler.build_entry(
        user_id=user_id,
        device_id=device_id,
        rom_id=rom_id,
        preserve_started_at=False,
    )
    if entry is None:
        return

    await _store_session(sid, user_id, device_id)
    await activity_handler.publish_active(entry)


@socket_handler.socket_server.on("activity:heartbeat")  # type: ignore
async def activity_heartbeat(sid: str, data: ActivityEventPayload) -> None:
    user_id = await _authenticated_user_id(sid)
    device_id, rom_id = _extract_payload(data)
    if user_id is None or device_id is None or rom_id is None:
        return

    entry = await activity_handler.build_entry(
        user_id=user_id,
        device_id=device_id,
        rom_id=rom_id,
        preserve_started_at=True,
    )
    if entry is None:
        return

    await _store_session(sid, user_id, device_id)
    await activity_handler.publish_active(entry)


@socket_handler.socket_server.on("activity:stop")  # type: ignore
async def activity_stop(sid: str, data: ActivityEventPayload | None = None) -> None:
    user_id = await _authenticated_user_id(sid)

    device_id: str | None = None
    if data:
        device_id, _ = _extract_payload(data)

    # Fall back to the device stored at start time if the payload omits it.
    if not device_id:
        device_id = (await _session(sid)).get("activity_device_id")

    if user_id is None or not device_id:
        return

    await activity_handler.publish_clear(int(user_id), device_id)


@socket_handler.socket_server.on("disconnect")  # type: ignore
async def activity_on_disconnect(sid: str) -> None:
    """Safety net: clear any activity tied to a disconnecting socket."""
    session = await _session(sid)
    user_id = session.get("activity_user_id")
    device_id = session.get("activity_device_id")
    if user_id is None or not device_id:
        return

    await activity_handler.publish_clear(int(user_id), device_id)
