import socketio  # type: ignore
from config import REDIS_URL
from utils import json as json_module


class SocketHandler:
    def __init__(self) -> None:
        self.socket_server = socketio.AsyncServer(
            cors_allowed_origins="*",
            async_mode="asgi",
            json=json_module,
            logger=False,
            engineio_logger=False,
            client_manager=socketio.AsyncRedisManager(str(REDIS_URL)),
        )

        self.socket_app = socketio.ASGIApp(
            self.socket_server, socketio_path="/ws/socket.io"
        )


socket_handler = SocketHandler()
