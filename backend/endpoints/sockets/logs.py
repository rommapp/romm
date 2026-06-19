"""Real-time backend log streaming over Socket.IO (admin only).

Pieces:
- ``connect`` handler on the main socket server: resolves the session user and,
  if they are an admin, joins them to the ``admin`` room. It never rejects a
  connection, so the existing scan/sync sockets keep working for everyone.
- ``start_log_forwarder``: a single background task (Redis-lock guarded) that
  subscribes to the ``romm:logs`` pub/sub channel — fed by ``LogStreamHandler``
  in every backend process — and relays each line to the ``admin`` room.
- ``get_recent_logs``: reads the capped ring buffer for backfill on view open.
"""

import asyncio
import uuid
from http.cookies import SimpleCookie
from typing import Any, Final

import socketio  # type: ignore

from config import REDIS_URL
from handler.database import db_user_handler
from handler.redis_handler import async_cache
from handler.socket_handler import socket_handler
from logger.log_stream_handler import LOG_BUFFER_KEY, LOG_CHANNEL
from logger.logger import log
from models.user import Role
from utils import json_module

ADMIN_ROOM: Final = "admin"
FORWARDER_LOCK_KEY: Final = "romm:logs:forwarder"
FORWARDER_LOCK_TTL: Final = 30  # seconds
# Session cookie name configured on RedisSessionMiddleware in main.py.
SESSION_COOKIE_NAME: Final = "romm_session"


async def _session_from_environ(environ: dict[str, Any]) -> dict[str, Any]:
    """Resolve the auth session for a socket handshake.

    Tries the session the middleware attached to the ASGI scope first; if it's
    absent (scope not propagated to the mounted socket app), falls back to
    parsing the session cookie and reading the session straight from Redis —
    the same lookup RedisSessionMiddleware performs.
    """
    scope = environ.get("asgi.scope", {})
    session = scope.get("session")
    if session:
        return session

    raw_cookie = environ.get("HTTP_COOKIE", "")
    if not raw_cookie:
        return {}

    cookie: SimpleCookie = SimpleCookie()
    cookie.load(raw_cookie)
    morsel = cookie.get(SESSION_COOKIE_NAME)
    if morsel is None:
        return {}

    session_data = await async_cache.get(f"session:{morsel.value}")
    if not session_data:
        return {}
    try:
        return json_module.loads(session_data)
    except Exception:  # noqa: BLE001 - malformed session is "no session"
        return {}


@socket_handler.socket_server.on("connect")  # type: ignore
async def connect(sid: str, environ: dict[str, Any], auth: Any = None) -> None:
    """Join admin users to the log-streaming room on socket connect.

    Always returns ``None`` (accepts the connection) — only the room membership
    is gated, so the existing scan/sync sockets keep working for everyone.
    """
    try:
        session = await _session_from_environ(environ)
        if session.get("iss") != "romm:auth":
            return

        username = session.get("sub")
        if not username:
            return

        user = db_user_handler.get_user_by_username(username)
        if user and user.enabled and user.role == Role.ADMIN:
            await socket_handler.socket_server.enter_room(sid, ADMIN_ROOM)
    except Exception:  # noqa: BLE001 - never let auth resolution refuse a socket
        log.exception("Failed to resolve admin for log stream connect")


async def get_recent_logs(limit: int) -> list[dict[str, Any]]:
    """Return the most recent buffered log lines in chronological order."""
    raw = await async_cache.lrange(LOG_BUFFER_KEY, 0, max(0, limit - 1))
    entries: list[dict[str, Any]] = []
    for item in raw:
        try:
            entries.append(json_module.loads(item))
        except Exception:  # noqa: BLE001 - skip malformed entry  # nosec B112
            continue
    # The buffer is newest-first (LPUSH); callers want oldest-first.
    entries.reverse()
    return entries


async def start_log_forwarder() -> None:
    """Relay log lines from Redis pub/sub to admin Socket.IO clients.

    Guarded by a Redis lock so that, when more than one web worker is running
    (WEB_SERVER_CONCURRENCY > 1), exactly one forwards and clients don't receive
    duplicate lines.
    """
    lock_id = str(uuid.uuid4())
    pubsub = None
    # Write-only manager for emitting — the same proven path scan/sync use. It
    # publishes the room emit to Redis; the main socket server's read-side
    # manager resolves `admin` room membership and delivers. Created inside the
    # running loop (like sync.py) rather than at import time.
    socket_manager = socketio.AsyncRedisManager(REDIS_URL, write_only=True)
    try:
        while True:
            got_lock = await async_cache.set(
                FORWARDER_LOCK_KEY, lock_id, nx=True, ex=FORWARDER_LOCK_TTL
            )
            if not got_lock:
                # Another worker owns the forwarder; check back periodically in
                # case it dies and the lock expires.
                await asyncio.sleep(FORWARDER_LOCK_TTL / 2)
                continue

            pubsub = async_cache.pubsub()
            await pubsub.subscribe(LOG_CHANNEL)
            log.info("Log stream forwarder started")
            try:
                while True:
                    # Heartbeat the lock so a healthy forwarder keeps ownership.
                    await async_cache.set(
                        FORWARDER_LOCK_KEY, lock_id, xx=True, ex=FORWARDER_LOCK_TTL
                    )
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=FORWARDER_LOCK_TTL / 3,
                    )
                    if not message:
                        continue
                    data = message.get("data")
                    if not data:
                        continue
                    # One bad message or emit must not kill the forwarder —
                    # swallow per-line and keep relaying.
                    try:
                        payload = json_module.loads(data)
                        await socket_manager.emit(
                            "logs:entry", payload, room=ADMIN_ROOM
                        )
                    except Exception:  # noqa: BLE001 - keep forwarding  # nosec B112
                        continue
            finally:
                await pubsub.unsubscribe(LOG_CHANNEL)
                await pubsub.aclose()  # type: ignore[attr-defined]
                pubsub = None
    except asyncio.CancelledError:
        if pubsub is not None:
            await pubsub.aclose()  # type: ignore[attr-defined]
        # Release the lock on shutdown so a restart (e.g. uvicorn --reload)
        # resumes forwarding immediately instead of waiting out the TTL.
        await _release_lock(lock_id)
        raise
    except Exception:  # noqa: BLE001 - never let the forwarder kill the app
        log.exception("Log forwarder crashed")
        await _release_lock(lock_id)


async def _release_lock(lock_id: str) -> None:
    """Delete the forwarder lock only if we still own it."""
    try:
        current = await async_cache.get(FORWARDER_LOCK_KEY)
        if current == lock_id:
            await async_cache.delete(FORWARDER_LOCK_KEY)
    except Exception:  # noqa: BLE001 - best-effort cleanup  # nosec B110
        pass
