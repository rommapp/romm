import socketio


socket_server = socketio.AsyncServer(
    cors_allowed_origins="*",
    async_mode="asgi",
    logger=False,
    engineio_logger=False,
    client_manager=socketio.AsyncRedisManager("redis://"),
)

socket_app = socketio.ASGIApp(socket_server)
