import socketio  # type: ignore

from utils.cache import redis_url, redis_connectable


socket_server = socketio.AsyncServer(
    cors_allowed_origins="*",
    async_mode="asgi",
    logger=False,
    engineio_logger=False,
    client_manager=socketio.AsyncRedisManager(redis_url) if redis_connectable else None,
)

socket_app = socketio.ASGIApp(socket_server)
