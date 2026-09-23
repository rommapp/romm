import asyncio
from typing import Any

import socketio

from config import REDIS_URL
from logger.logger import log
from utils import json_module


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

    def write_manager(self) -> socketio.AsyncRedisManager:
        """A publish-only manager on this server's channel, usable from an RQ worker."""
        # A Redis client is bound to the loop that made it, and a worker runs
        # each job in a new loop.
        loop = asyncio.get_running_loop()
        if self._write_manager is None or self._write_manager_loop is not loop:
            self._write_manager = socketio.AsyncRedisManager(
                REDIS_URL, channel=self.channel, write_only=True
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


socket_handler = SocketHandler(path="/ws/socket.io")
# Netplay clients are unauthenticated and name their own rooms, so they must not
# share a channel where `user:{id}` and `admin` rooms are addressed.
netplay_socket_handler = SocketHandler(path="/netplay/socket.io", channel="netplay")
