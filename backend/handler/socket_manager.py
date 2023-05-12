import socketio


class SocketManager(object):
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(SocketManager, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        self.server = socketio.AsyncServer(
            cors_allowed_origins="*",
            async_mode="asgi",
            logger=False,
            engineio_logger=False,
        )
        self.app = socketio.ASGIApp(self.server)

    @property
    def on(self):
        return self.server.on

    @property
    def send(self):
        return self.server.send
    
    @property
    def emit(self):
        return self.server.emit

    def mount_to(self, path: str, app):
        app.mount(path, self.app)
