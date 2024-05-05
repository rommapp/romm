import socketio  # type: ignore
from handler.redis_handler import redis_url


class SocketHandler:
    def __init__(self) -> None:
        self.socket_server = socketio.AsyncServer(
            cors_allowed_origins="*",
            async_mode="asgi",
            logger=False,
            engineio_logger=False,
            client_manager=socketio.AsyncRedisManager(redis_url),
        )

        self.socket_app = socketio.ASGIApp(self.socket_server, socketio_path="/ws/socket.io")

socket_handler = SocketHandler()
