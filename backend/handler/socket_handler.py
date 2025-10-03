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
            ping_timeout=60,
            ping_interval=25,
            max_http_buffer_size=1e6,  # 1MB
            cors_credentials=True,
        )

        self.socket_app = socketio.ASGIApp(
            self.socket_server, socketio_path="/ws/socket.io"
        )

        # Register connection handlers
        self.socket_server.on("connect")(self.on_connect)  # type: ignore
        self.socket_server.on("disconnect")(self.on_disconnect)  # type: ignore

    async def on_connect(
        self, sid: str, environ: dict, auth: dict | None = None
    ) -> None:
        """Handle socket connection and store session data."""
        # Extract session data from the request environment
        session_data = {}

        # Create a mock scope for session extraction
        scope = {
            "type": "websocket",
            "headers": [
                (k.encode("latin-1"), v.encode("latin-1"))
                for k, v in environ.items()
                if k.startswith("HTTP_")
            ],
        }

        # Try to extract session using the session middleware
        try:
            # Extract session from cookies
            from starlette.requests import HTTPConnection

            connection = HTTPConnection(scope)

            # Manually extract session cookie
            if "HTTP_COOKIE" in environ:
                cookies = environ["HTTP_COOKIE"]
                for cookie in cookies.split(";"):
                    if "romm_session=" in cookie:
                        cookie_value = (
                            cookie.strip().split("romm_session=")[1].split(";")[0]
                        )
                        # Store the raw cookie value for later JWT decoding
                        session_data["session_cookie"] = cookie_value
                        break

            # Store the parsed session data
            session_data["session"] = connection.session
            session_data["headers"] = scope["headers"]

        except Exception:
            # If session extraction fails, store empty session
            session_data["session"] = {}
            session_data["headers"] = scope["headers"]

        # Store session data in the socket manager
        await self.socket_server.save_session(sid, session_data)

    async def on_disconnect(self, sid: str) -> None:
        """Handle socket disconnection."""
        # Clean up session data
        await self.socket_server.save_session(sid, {})


socket_handler = SocketHandler()
