import socketio

from worker import redis_url


socket_server = socketio.AsyncServer(
    cors_allowed_origins="*",
    async_mode="asgi",
    logger=False,
    engineio_logger=False,
    client_manager=socketio.AsyncRedisManager(redis_url),
)

socket_app = socketio.ASGIApp(socket_server)
