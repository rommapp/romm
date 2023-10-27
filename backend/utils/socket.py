import socketio  # type: ignore

from utils.cache import redis_url
from config import ENABLE_EXPERIMENTAL_REDIS


socket_server = socketio.AsyncServer(
    cors_allowed_origins="*",
    async_mode="asgi",
    logger=False,
    engineio_logger=False,
    client_manager=socketio.AsyncRedisManager(redis_url)
    if ENABLE_EXPERIMENTAL_REDIS
    else None,
)

socket_app = socketio.ASGIApp(socket_server)
