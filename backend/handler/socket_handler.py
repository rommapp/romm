import asyncio
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Final

import socketio

from config import REDIS_URL, SESSION_MAX_AGE_SECONDS
from handler.redis_handler import async_cache
from logger.logger import log
from utils import json_module

if TYPE_CHECKING:
    from models.user import User

# Where a socket's own session records the login session that opened it.
LOGIN_SESSION_ID_KEY: Final = "login_session_id"


class SocketHandler:
    def __init__(self, path: str, channel: str = "socketio") -> None:
        self.channel = channel
        self.socket_server = socketio.AsyncServer(
            cors_allowed_origins="*",
            async_mode="asgi",
            json=json_module,
            logger=False,
            engineio_logger=False,
            client_manager=socketio.AsyncRedisManager(REDIS_URL, channel=channel),
            ping_timeout=60,
            ping_interval=25,
            max_http_buffer_size=1e6,  # 1MB
            cors_credentials=True,
        )

        self.socket_app = socketio.ASGIApp(self.socket_server, socketio_path=path)

        self._write_manager: socketio.AsyncRedisManager | None = None
        self._write_manager_loop: asyncio.AbstractEventLoop | None = None

    def _login_session_sockets_key(self, session_id: str) -> str:
        # Per channel, since a sid only means something to the server that issued it.
        return f"session_sockets:{self.channel}:{session_id}"

    def write_manager(self) -> socketio.AsyncRedisManager:
        """A publish-only manager on this server's channel, usable from an RQ worker."""
        # A Redis client is bound to the loop that made it, and a worker runs
        # each job in a new loop.
        loop = asyncio.get_running_loop()
        if self._write_manager is None or self._write_manager_loop is not loop:
            # Only a manager attached to a server inherits its JSON encoder.
            self._write_manager = socketio.AsyncRedisManager(
                REDIS_URL, channel=self.channel, write_only=True, json=json_module
            )
            self._write_manager_loop = loop
        return self._write_manager

    async def emit_to_user(
        self, user_id: int, event: str, payload: dict[str, Any]
    ) -> None:
        """Push an event to every open tab of one user, logging a failure."""
        try:
            await self.write_manager().emit(event, payload, room=f"user:{user_id}")
        except Exception:  # noqa: BLE001
            log.warning(f"Failed to push {event} to user {user_id}", exc_info=True)

    async def get_session(self, sid: str) -> dict[str, Any]:
        """The socket's server-side session, empty once the socket is gone."""
        try:
            return await self.socket_server.get_session(sid) or {}
        except KeyError:
            return {}

    async def authenticate(self, sid: str, environ: dict[str, Any]) -> "User | None":
        """The enabled user behind a handshake's login session, binding the socket to it."""
        # Deferred: both import the auth middleware, which imports this module.
        from handler.database import db_user_handler
        from utils.auth import get_session_from_environ

        session = await get_session_from_environ(environ)
        username = session.get("sub")
        if session.get("iss") != "romm:auth" or not username:
            return None

        user = db_user_handler.get_user_by_username(username)
        if not user or not user.enabled:
            return None

        session_id = session.get("session_id")
        if session_id:
            await self.bind_to_login_session(sid, session_id)
        return user

    async def bind_to_login_session(self, sid: str, session_id: str) -> None:
        """Record which login session opened a socket, so revoking it closes the socket."""
        key = self._login_session_sockets_key(session_id)
        await async_cache.sadd(key, sid)
        await async_cache.expire(key, SESSION_MAX_AGE_SECONDS)
        async with self.socket_server.session(sid) as session:
            session[LOGIN_SESSION_ID_KEY] = session_id

    async def unbind_from_login_session(self, sid: str) -> None:
        """Forget a disconnecting socket, logging a failure."""
        try:
            session_id = (await self.get_session(sid)).get(LOGIN_SESSION_ID_KEY)
            if session_id:
                await async_cache.srem(self._login_session_sockets_key(session_id), sid)
        except Exception:  # noqa: BLE001
            log.warning(f"Failed to unbind socket {sid}", exc_info=True)

    async def close_login_sessions(self, session_ids: Iterable[str]) -> None:
        """Disconnect every socket the given login sessions opened, on any worker.

        A socket keeps the rooms its session earned at connect, so a revoked
        session would otherwise go on receiving its user's and the admins' events.
        """
        for session_id in session_ids:
            key = self._login_session_sockets_key(session_id)
            try:
                sids = await async_cache.smembers(key)
                await async_cache.delete(key)
                for sid in sids:
                    # A socket on another worker is disconnected through the broker.
                    await self.socket_server.disconnect(
                        sid.decode() if isinstance(sid, bytes) else sid
                    )
            except Exception:  # noqa: BLE001
                log.warning(
                    f"Failed to close the sockets of session {session_id}",
                    exc_info=True,
                )


socket_handler = SocketHandler(path="/ws/socket.io")
# Netplay clients may be anonymous guests and name their own rooms, so they must
# not share a channel where `user:{id}` and `admin` rooms are addressed.
netplay_socket_handler = SocketHandler(path="/netplay/socket.io", channel="netplay")


async def close_login_session_sockets(session_ids: Iterable[str]) -> None:
    """Disconnect the sockets the given login sessions opened, on every server."""
    ids = list(session_ids)
    await asyncio.gather(
        socket_handler.close_login_sessions(ids),
        netplay_socket_handler.close_login_sessions(ids),
    )
