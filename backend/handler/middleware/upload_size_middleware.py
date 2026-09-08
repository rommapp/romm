from re import Pattern

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class UploadSizeLimitMiddleware:
    """Reject oversized uploads on the given paths from their Content-Length.

    FastAPI resolves `UploadFile` parameters (spooling the whole multipart body
    to temporary storage) before the endpoint runs, so a handler-level size
    check cannot prevent the disk usage it is meant to bound. Rejecting here,
    before the body is read, is what actually caps it.
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
                    {
                        "detail": (
                            f"Request body exceeds the maximum allowed size of "
                            f"{self.max_size} bytes"
                        )
                    },
                    status_code=413,
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)
