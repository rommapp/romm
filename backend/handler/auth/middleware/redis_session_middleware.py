import json
import uuid

from starlette.datastructures import MutableHeaders
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from config import SESSION_MAX_AGE_SECONDS
from handler.redis_handler import async_cache


class RedisSessionMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        session_cookie: str = "session",
        max_age: int = SESSION_MAX_AGE_SECONDS,
        same_site: str = "lax",
        https_only: bool = False,
    ) -> None:
        self.app = app
        self.session_cookie = session_cookie
        self.max_age = max_age
        self.security_flags = "httponly; samesite=" + same_site
        if https_only:
            self.security_flags += "; secure"

    @staticmethod
    async def clear_user_sessions(user_id: str) -> None:
        """
        Clears all active sessions for a given user.
        """
        session_ids = await async_cache.smembers(f"user_sessions:{user_id}")
        if not session_ids:
            return

        # A member comes back as bytes from a client that does not decode, and
        # it goes straight into a key name, where its repr would miss the
        # session and leave it live.
        keys = [
            f"session:{sid.decode() if isinstance(sid, bytes) else sid}"
            for sid in session_ids
        ]
        await async_cache.delete(*keys, f"user_sessions:{user_id}")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        connection = HTTPConnection(scope)
        session_id = None
        initial_user_id = None
        session_cookie_from_request = connection.cookies.get(self.session_cookie)

        if session_cookie_from_request:
            session_id = session_cookie_from_request
            session_data = await async_cache.get(f"session:{session_id}")
            if session_data:
                scope["session"] = json.loads(session_data)
                scope["session"]["session_id"] = session_id
                initial_user_id = scope["session"].get("sub")
            else:
                scope["session"] = {}
        else:
            scope["session"] = {}

        async def send_wrapper(message: Message) -> None:
            nonlocal session_id
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                # Check for user_id to track user-specific sessions
                user_id = scope["session"].get("sub")

                if scope["session"]:
                    existing_id = scope["session"].pop("session_id", None)
                    session_id = existing_id or str(uuid.uuid4())
                    session_data_json = json.dumps(scope["session"])
                    # One already in Redis is refreshed only while its record is
                    # still there. A credential change revokes sessions through
                    # `clear_user_sessions`, and a request already in flight when
                    # that happens would otherwise write its copy back and undo it.
                    stored = await async_cache.set(
                        f"session:{session_id}",
                        session_data_json,
                        ex=self.max_age,
                        xx=existing_id is not None,
                    )

                    if stored:
                        # Add session_id to user set of sessions
                        if user_id:
                            await async_cache.sadd(
                                f"user_sessions:{user_id}", session_id
                            )

                        header_value = f"{self.session_cookie}={session_id}; path=/; Max-Age={self.max_age}; {self.security_flags}"
                    else:
                        header_value = f"{self.session_cookie}=null; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; {self.security_flags}"

                    headers.append("Set-Cookie", header_value)
                elif session_id:
                    await async_cache.delete(f"session:{session_id}")
                    # Remove session_id from user set of sessions
                    if initial_user_id:
                        await async_cache.srem(
                            f"user_sessions:{initial_user_id}", session_id
                        )

                    header_value = f"{self.session_cookie}=null; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; {self.security_flags}"
                    headers.append("Set-Cookie", header_value)

            await send(message)

        await self.app(scope, receive, send_wrapper)
