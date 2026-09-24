from re import Pattern

from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class UploadSizeLimitMiddleware:
    """Reject oversized uploads on the given paths before they are spooled.

    FastAPI resolves `UploadFile` parameters (spooling the whole multipart body
    to temporary storage) before the endpoint runs, so a handler-level size
    check cannot prevent the disk usage it is meant to bound. A declared
    Content-Length is rejected up front; a chunked body is cut off once it
    streams past the limit.
    """

    UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH"})

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_size: int,
        paths: list[Pattern],
    ) -> None:
        self.app = app
        self.max_size = max_size
        self.paths = paths

    def _too_large_detail(self) -> str:
        return f"Request body exceeds the maximum allowed size of {self.max_size} bytes"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or not self.max_size
            or scope["method"] not in self.UNSAFE_METHODS
            or not any(pattern.match(scope["path"]) for pattern in self.paths)
        ):
            await self.app(scope, receive, send)
            return

        content_length = Headers(scope=scope).get("content-length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError:
                response = JSONResponse(
                    {"detail": "Invalid Content-Length header"}, status_code=400
                )
                await response(scope, receive, send)
                return

            if declared_size > self.max_size:
                response = JSONResponse(
                    {"detail": self._too_large_detail()}, status_code=413
                )
                await response(scope, receive, send)
                return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                # FastAPI re-raises an HTTPException from body parsing, so the
                # app's exception handling turns this into the 413.
                if received > self.max_size:
                    raise HTTPException(
                        status_code=413, detail=self._too_large_detail()
                    )
            return message

        await self.app(scope, limited_receive, send)
