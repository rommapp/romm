"""Test suite for RedisSessionMiddleware's Redis-backed session persistence."""

from unittest.mock import AsyncMock

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from handler.auth.constants import SESSION_COOKIE_NAME
from handler.auth.middleware import redis_session_middleware
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

    async def logout(request: Request) -> JSONResponse:
        request.session.clear()
        return JSONResponse({"ok": True})

    return Starlette(
        routes=[
            Route("/login", login, methods=["POST"]),
            Route("/revoke", revoke, methods=["POST"]),
            Route("/whoami", whoami, methods=["GET"]),
            Route("/logout", logout, methods=["POST"]),
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


class TestRevokedSessionsCloseTheirSockets:
    @pytest.fixture
    def close_login_sessions(self, mocker):
        return mocker.patch.object(
            redis_session_middleware, "close_login_session_sockets", AsyncMock()
        )

    def test_logging_out_closes_that_sessions_sockets(
        self, close_login_sessions
    ) -> None:
        client = TestClient(create_test_app())
        session_id = client.post("/login").cookies[SESSION_COOKIE_NAME]

        client.post("/logout")

        close_login_sessions.assert_awaited_once_with([session_id])

    def test_revoking_a_users_sessions_closes_all_their_sockets(
        self, close_login_sessions
    ) -> None:
        phone, laptop = TestClient(create_test_app()), TestClient(create_test_app())
        ids = {
            phone.post("/login").cookies[SESSION_COOKIE_NAME],
            laptop.post("/login").cookies[SESSION_COOKIE_NAME],
        }

        phone.post("/revoke")

        assert ids <= set(close_login_sessions.await_args.args[0])

    def test_a_cookie_for_a_gone_session_closes_nothing(
        self, close_login_sessions
    ) -> None:
        client = TestClient(create_test_app())
        client.cookies.set(SESSION_COOKIE_NAME, "not-a-real-session")

        client.post("/logout")

        close_login_sessions.assert_not_awaited()
