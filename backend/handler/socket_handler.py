import asyncio
from collections.abc import Awaitable, Callable, Iterable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Final

import socketio

from config import REDIS_URL, SESSION_MAX_AGE_SECONDS
from handler.redis_handler import REDIS_CLIENT_OPTIONS, as_text, async_cache
from logger.logger import log
from utils import json_module
from utils.background_tasks import fire_and_forget
from utils.datetime import to_utc

if TYPE_CHECKING:
    from handler.auth.hybrid_auth import ClientTokenIdentity
    from models.user import User

# Where a socket's own session records the login session that opened it.
LOGIN_SESSION_ID_KEY: Final = "login_session_id"
# Where a socket's own session records the client token that opened it.
CLIENT_TOKEN_ID_SESSION_KEY: Final = "client_token_id"
DEVICES_NAMESPACE: Final = "/devices"
# How often a token socket's tracking is renewed while it stays connected.
TOKEN_TRACKING_REFRESH_SECONDS: Final = SESSION_MAX_AGE_SECONDS / 2


def client_token_sockets_key(token_id: int) -> str:
    return f"device_token_sockets:{token_id}"


def raw_client_token_from_handshake(
    environ: dict[str, Any], auth: Any = None
) -> str | None:
    """The token from the handshake's auth payload, else its bearer header."""
    token = auth.get("token") if isinstance(auth, dict) else None
    if isinstance(token, str) and token:
        return token

    scheme, _, credentials = str(environ.get("HTTP_AUTHORIZATION", "")).partition(" ")
    if scheme.lower() != "bearer" or not credentials:
        return None
    return credentials.strip()


class SocketHandler:
    def __init__(self, path: str, channel: str = "socketio") -> None:
        self.channel = channel
        self.socket_server = socketio.AsyncServer(
            cors_allowed_origins="*",
            async_mode="asgi",
            json=json_module,
            logger=False,
            engineio_logger=False,
            client_manager=socketio.AsyncRedisManager(
                REDIS_URL, channel=channel, redis_options=REDIS_CLIENT_OPTIONS
            ),
            ping_timeout=60,
            ping_interval=25,
            max_http_buffer_size=1e6,  # 1MB
            cors_credentials=True,
        )

        self.socket_app = socketio.ASGIApp(self.socket_server, socketio_path=path)

        self._write_manager: socketio.AsyncRedisManager | None = None
        self._write_manager_loop: asyncio.AbstractEventLoop | None = None

    def on[F: Callable[..., Awaitable[object]]](
        self, event: str, namespace: str | None = None
    ) -> Callable[[F], F]:
        """Register a socket event handler without changing its signature."""

        def register(handler: F) -> F:
            self.socket_server.on(event, handler, namespace=namespace)
            return handler

        return register

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
                REDIS_URL,
                channel=self.channel,
                write_only=True,
                json=json_module,
                redis_options=REDIS_CLIENT_OPTIONS,
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

    async def get_session(
        self, sid: str, namespace: str | None = None
    ) -> dict[str, Any]:
        """The socket's server-side session, empty once the socket is gone."""
        try:
            return await self.socket_server.get_session(sid, namespace=namespace) or {}
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
        if session_id and not await self.bind_to_login_session(sid, session_id):
            return None
        return user

    def _token_tracking_key(self, token_id: int, namespace: str | None) -> str:
        """The token's socket set for this server and namespace, so closing one set cannot consume another's."""
        return f"{client_token_sockets_key(token_id)}:{self.channel}:{namespace or 'default'}"

    async def authenticate_client_token(
        self,
        sid: str,
        environ: dict[str, Any],
        auth: Any = None,
        *,
        namespace: str | None = None,
    ) -> "ClientTokenIdentity | None":
        """The live client-token identity behind a handshake, binding the socket for revocation."""
        # Deferred: both import the auth middleware, which imports this module.
        from handler.auth.constants import CLIENT_TOKEN_PREFIX
        from handler.auth.hybrid_auth import resolve_client_token
        from handler.database import db_client_token_handler

        raw_token = raw_client_token_from_handshake(environ, auth)
        if not raw_token or not raw_token.startswith(CLIENT_TOKEN_PREFIX):
            return None

        identity = resolve_client_token(raw_token)
        if identity is None:
            return None

        token_id = identity.token.id
        tracking_key = self._token_tracking_key(token_id, namespace)
        await self.track(tracking_key, sid, SESSION_MAX_AGE_SECONDS)
        # A revocation that ran before the socket was tracked found nothing to close.
        refreshed = resolve_client_token(raw_token)
        if refreshed is None or refreshed.token.id != token_id:
            await self.untrack(tracking_key, sid)
            return None

        db_client_token_handler.update_last_used(token_id)
        async with self.socket_server.session(sid, namespace=namespace) as session:
            session[CLIENT_TOKEN_ID_SESSION_KEY] = token_id
        expires_at = identity.token.expires_at
        fire_and_forget(
            self._keep_token_tracked(
                sid, token_id, to_utc(expires_at) if expires_at else None, namespace
            )
        )
        return identity

    async def _keep_token_tracked(
        self,
        sid: str,
        token_id: int,
        expires_at: datetime | None,
        namespace: str | None,
    ) -> None:
        """Renew a token socket's tracking until it disconnects or its token expires."""
        server = self.socket_server
        while True:
            await server.sleep(TOKEN_TRACKING_REFRESH_SECONDS)
            if not server.manager.is_connected(sid, namespace or "/"):
                return
            if expires_at and expires_at <= datetime.now(timezone.utc):
                await server.disconnect(sid, namespace=namespace)
                return
            try:
                await self.track(
                    self._token_tracking_key(token_id, namespace),
                    sid,
                    SESSION_MAX_AGE_SECONDS,
                )
            except Exception:  # noqa: BLE001
                log.warning(
                    f"Failed to refresh the tracking of token {token_id}",
                    exc_info=True,
                )

    async def unbind_from_client_token(
        self, sid: str, *, namespace: str | None = None
    ) -> None:
        """Forget which client token opened a socket, if any, on disconnect."""
        token_id = (await self.get_session(sid, namespace=namespace)).get(
            CLIENT_TOKEN_ID_SESSION_KEY
        )
        if token_id is not None:
            await self.untrack(self._token_tracking_key(token_id, namespace), sid)

    async def track(
        self, key: str, sid: str, ttl_seconds: int, *, while_exists: str | None = None
    ) -> bool:
        """Add a socket to the set under ``key`` and restart its expiry.

        Returns:
            False when ``while_exists`` names a key that is gone, leaving nothing added
        """
        # One transaction, so a dropped connection cannot leave the set without its TTL.
        async with async_cache.pipeline() as pipe:
            await pipe.sadd(key, sid)
            await pipe.expire(key, ttl_seconds)
            if while_exists:
                await pipe.exists(while_exists)
            results = await pipe.execute()
        if while_exists and not results[-1]:
            await async_cache.srem(key, sid)
            return False
        return True

    async def untrack(self, key: str, sid: str) -> None:
        """Drop a socket from the set under ``key``, logging a failure."""
        try:
            await async_cache.srem(key, sid)
        except Exception:  # noqa: BLE001
            log.warning(f"Failed to forget socket {sid} under {key}", exc_info=True)

    async def close_tracked(self, key: str, namespace: str | None = None) -> None:
        """Disconnect every socket tracked under ``key`` on any worker, logging a failure."""
        try:
            # One transaction, so a socket tracked in between is not dropped from
            # the set without being disconnected.
            async with async_cache.pipeline() as pipe:
                await pipe.smembers(key)
                await pipe.delete(key)
                sids, _ = await pipe.execute()
        except Exception:  # noqa: BLE001
            log.warning(f"Failed to close the sockets under {key}", exc_info=True)
            return
        for sid in sids:
            try:
                # A socket on another worker is disconnected through the broker.
                await self.socket_server.disconnect(as_text(sid), namespace=namespace)
            except Exception:  # noqa: BLE001
                log.warning(f"Failed to close socket {as_text(sid)}", exc_info=True)

    async def bind_to_login_session(self, sid: str, session_id: str) -> bool:
        """Record which login session opened a socket, so revoking it closes the socket.

        Returns:
            False when the session was revoked first, leaving the socket unbound
        """
        # Revocation deletes the session before reading the set, so a session
        # still there after the add means revocation will see this socket.
        if not await self.track(
            self._login_session_sockets_key(session_id),
            sid,
            SESSION_MAX_AGE_SECONDS,
            while_exists=f"session:{session_id}",
        ):
            return False
        async with self.socket_server.session(sid) as session:
            session[LOGIN_SESSION_ID_KEY] = session_id
        return True

    async def unbind_from_login_session(self, sid: str) -> None:
        """Forget a disconnecting socket, logging a failure."""
        try:
            session_id = (await self.get_session(sid)).get(LOGIN_SESSION_ID_KEY)
            if session_id:
                await self.untrack(self._login_session_sockets_key(session_id), sid)
        except Exception:  # noqa: BLE001
            log.warning(f"Failed to unbind socket {sid}", exc_info=True)

    async def close_login_sessions(self, session_ids: Iterable[str]) -> None:
        """Disconnect every socket the given login sessions opened, on any worker.

        A socket keeps the rooms its session earned at connect, so a revoked
        session would otherwise go on receiving its user's and the admins' events.
        """
        for session_id in session_ids:
            await self.close_tracked(self._login_session_sockets_key(session_id))


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


async def close_client_token_sockets(token_ids: Iterable[int]) -> None:
    """Disconnect every socket the given client tokens opened, on any worker."""
    for token_id in token_ids:
        await asyncio.gather(
            socket_handler.close_tracked(
                client_token_sockets_key(token_id), DEVICES_NAMESPACE
            ),
            socket_handler.close_tracked(
                socket_handler._token_tracking_key(token_id, None)
            ),
            netplay_socket_handler.close_tracked(
                netplay_socket_handler._token_tracking_key(token_id, None)
            ),
        )
