import socketio  # type: ignore

from utils.cache import redis_url, use_redis_connection


socket_server = socketio.AsyncServer(
    cors_allowed_origins="*",
    async_mode="asgi",
    logger=False,
    engineio_logger=False,
    client_manager=socketio.AsyncRedisManager(redis_url) if use_redis_connection else None,
)

socket_app = socketio.ASGIApp(socket_server)
