import re

from fastapi import FastAPI, UploadFile
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient
from urllib3 import encode_multipart_formdata

from handler.middleware.upload_size_middleware import UploadSizeLimitMiddleware


def create_test_app(max_size: int) -> Starlette:
    async def handler(request: Request) -> JSONResponse:
        body = await request.body()
        return JSONResponse({"received": len(body)})

    return Starlette(
        routes=[
            Route("/api/saves", handler, methods=["GET", "POST"]),
            Route("/api/roms", handler, methods=["POST"]),
        ],
        middleware=[
            Middleware(
                UploadSizeLimitMiddleware,
                max_size=max_size,
                paths=[re.compile(r"^/api/saves")],
            )
        ],
    )


class TestUploadSizeLimitMiddleware:
    def test_rejects_oversized_body(self):
        client = TestClient(create_test_app(max_size=10))
        response = client.post("/api/saves", content=b"x" * 11)

        assert response.status_code == 413
        assert "maximum allowed size" in response.json()["detail"]

    def test_allows_body_at_the_limit(self):
        client = TestClient(create_test_app(max_size=10))
        response = client.post("/api/saves", content=b"x" * 10)

        assert response.status_code == 200
        assert response.json() == {"received": 10}

    def test_rejects_malformed_content_length(self):
        client = TestClient(create_test_app(max_size=10))
        response = client.post(
            "/api/saves", content=b"x", headers={"content-length": "not-a-number"}
        )

        assert response.status_code == 400

    def test_ignores_unguarded_paths(self):
        client = TestClient(create_test_app(max_size=10))
        response = client.post("/api/roms", content=b"x" * 100)

        assert response.status_code == 200

    def test_ignores_safe_methods(self):
        client = TestClient(create_test_app(max_size=10))
        response = client.get("/api/saves")

        assert response.status_code == 200

    def test_disabled_when_max_size_is_zero(self):
        client = TestClient(create_test_app(max_size=0))
        response = client.post("/api/saves", content=b"x" * 100)

        assert response.status_code == 200

    def test_rejects_chunked_body_past_the_limit(self):
        client = TestClient(create_test_app(max_size=10))
        response = client.post("/api/saves", content=iter([b"x" * 6, b"x" * 5]))

        assert response.status_code == 413
        assert "maximum allowed size" in response.text

    def test_allows_chunked_body_at_the_limit(self):
        client = TestClient(create_test_app(max_size=10))
        response = client.post("/api/saves", content=iter([b"x" * 5, b"x" * 5]))

        assert response.status_code == 200
        assert response.json() == {"received": 10}

    def test_rejects_chunked_multipart_upload_past_the_limit(self):
        app = FastAPI()

        @app.post("/api/saves")
        async def upload(file: UploadFile) -> dict[str, int]:
            return {"received": len(await file.read())}

        app.add_middleware(
            UploadSizeLimitMiddleware, max_size=100, paths=[re.compile(r"^/api/saves")]
        )
        body, content_type = encode_multipart_formdata(
            {"file": ("save.srm", b"x" * 200)}
        )
        response = TestClient(app).post(
            "/api/saves", content=iter([body]), headers={"content-type": content_type}
        )

        assert response.status_code == 413
