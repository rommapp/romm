import typing
from starlette.types import Send
from starlette.background import BackgroundTask
from starlette.responses import ContentStream
from starlette.concurrency import iterate_in_threadpool
from fastapi.responses import StreamingResponse

from utils.socket import socket_server


class CustomStreamingResponse(StreamingResponse):
    def __init__(
        self,
        content: ContentStream,
        status_code: int = 200,
        headers: typing.Optional[typing.Mapping[str, str]] = None,
        media_type: typing.Optional[str] = None,
        background: typing.Optional[BackgroundTask] = None,
        emit_body: dict = {},
    ) -> None:
        if isinstance(content, typing.AsyncIterable):
            self.body_iterator = content
        else:
            self.body_iterator = iterate_in_threadpool(content)
        self.status_code = status_code
        self.media_type = self.media_type if media_type is None else media_type
        self.background = background
        self.emit_body = emit_body
        self.init_headers(headers)

    async def stream_response(self, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.raw_headers,
            }
        )
        async for chunk in self.body_iterator:
            if not isinstance(chunk, bytes):
                chunk = chunk.encode(self.charset)
            await send({"type": "http.response.body", "body": chunk, "more_body": True})

        await socket_server.emit("download:complete", self.emit_body)
        await send({"type": "http.response.body", "body": b"", "more_body": False})
