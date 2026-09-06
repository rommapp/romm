"""Socket.IO notifications for launcher clients (the desktop companion).

Emits ``shortcuts:changed`` with only the device id: the client fetches its
queue over REST, which keeps the event idempotent and free of anything
sensitive. It goes to the ``device:<id>`` room a device-bound client token
joins on connect, and to the owner's ``user:<id>`` room so open web clients
refresh button state without polling. A write-only Redis manager keeps this
callable from any worker.
"""

import socketio  # type: ignore

from config import REDIS_URL

DEVICE_ROOM_PREFIX = "device:"


def device_room(device_id: str) -> str:
    return f"{DEVICE_ROOM_PREFIX}{device_id}"


def _get_socket_manager() -> socketio.AsyncRedisManager:
    return socketio.AsyncRedisManager(REDIS_URL, write_only=True)


async def emit_shortcuts_changed(device_id: str, user_id: int) -> None:
    sm = _get_socket_manager()
    payload = {"device_id": device_id}
    await sm.emit("shortcuts:changed", payload, room=device_room(device_id))
    await sm.emit("shortcuts:changed", payload, room=f"user:{user_id}")
