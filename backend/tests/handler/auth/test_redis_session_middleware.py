"""Test suite for RedisSessionMiddleware's Redis-backed session persistence."""

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from handler.auth.constants import SESSION_COOKIE_NAME
from handler.auth.middleware.redis_session_middleware import RedisSessionMiddleware

USERNAME = "user_1"


def create_test_app() -> Starlette:
    async def login(request: Request) -> JSONResponse:
        request.session["iss"] = "romm:auth"
        request.session["sub"] = USERNAME
        return JSONResponse({"ok": True})

    async def revoke(request: Request) -> JSONResponse:
        """Revoke the caller's sessions while their own request is in flight."""
        await RedisSessionMiddleware.clear_user_sessions(USERNAME)
        return JSONResponse({"ok": True})

    async def whoami(request: Request) -> JSONResponse:
        return JSONResponse({"sub": request.session.get("sub")})

    return Starlette(
        routes=[
            Route("/login", login, methods=["POST"]),
            Route("/revoke", revoke, methods=["POST"]),
            Route("/whoami", whoami, methods=["GET"]),
        ],
        middleware=[
            Middleware(
                RedisSessionMiddleware,
                session_cookie=SESSION_COOKIE_NAME,
                same_site="strict",
                https_only=False,
            )
        ],
    )


class TestRedisSessionMiddleware:
    def test_session_survives_across_requests(self) -> None:
        client = TestClient(create_test_app())

        assert client.post("/login").status_code == 200
        assert client.get("/whoami").json()["sub"] == USERNAME

    def test_revoked_session_is_not_restored_by_an_in_flight_request(self) -> None:
        """A session revoked mid-flight must not be written back."""
        client = TestClient(create_test_app())
        client.post("/login")

        client.post("/revoke")

        assert client.get("/whoami").json()["sub"] is None

    def test_a_cookie_for_an_unknown_session_gets_a_fresh_id(self) -> None:
        client = TestClient(create_test_app())
        client.cookies.set(SESSION_COOKIE_NAME, "not-a-real-session")

        response = client.post("/login")

        assert response.cookies[SESSION_COOKIE_NAME] != "not-a-real-session"
