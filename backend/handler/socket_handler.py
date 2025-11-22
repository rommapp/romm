import socketio  # type: ignore

from config import REDIS_URL
from utils import json_module


class SocketHandler:
    def __init__(self, path: str = "/ws/socket.io") -> None:
        self.socket_server = socketio.AsyncServer(
            cors_allowed_origins="*",
            async_mode="asgi",
            json=json_module,
            logger=False,
            engineio_logger=False,
            client_manager=socketio.AsyncRedisManager(REDIS_URL),
            ping_timeout=60,
            ping_interval=25,
            max_http_buffer_size=1e6,  # 1MB
            cors_credentials=True,
        )

        self.socket_app = socketio.ASGIApp(self.socket_server, socketio_path=path)


socket_handler = SocketHandler()
netplay_socket_handler = SocketHandler(path="/netplay/socket.io")
