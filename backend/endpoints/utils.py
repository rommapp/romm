from fastapi.responses import StreamingResponse

from utils.socket import socket_server


class CustomStreamingResponse(StreamingResponse):
    def __init__(self, *args, **kwargs) -> None:
        self.emit_body = kwargs.pop("emit_body", None)
        super().__init__(*args, **kwargs)

    async def stream_response(self, *args, **kwargs) -> None:
        await super().stream_response(*args, **kwargs)
        await socket_server.emit("download:complete", self.emit_body)
