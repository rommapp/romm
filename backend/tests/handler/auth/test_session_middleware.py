"""
Test suite for SessionMiddleware using JWT-based session management.
"""

import time
from typing import Any, Dict

from joserfc import jwt
from joserfc.jwk import OctKey
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from handler.auth.middleware.session_middleware import SessionMiddleware


def create_test_app(**middleware_kwargs) -> Starlette:
    # Test app routes
    async def homepage(request: Request) -> PlainTextResponse:
        """Basic route that sets default session data."""
        request.session.setdefault("visited", 0)
        request.session["visited"] += 1
        return PlainTextResponse("OK")

    async def set_session(request: Request) -> JSONResponse:
        """Set specific session data."""
        data = await request.json()
        request.session.update(data)
        return JSONResponse({"session": dict(request.session)})

    async def get_session(request: Request) -> JSONResponse:
        """Get current session data."""
        return JSONResponse({"session": dict(request.session)})

    async def clear_session_route(request: Request) -> PlainTextResponse:
        """Clear the session."""
        request.session.clear()
        return PlainTextResponse("Session cleared")

    async def modify_session(request: Request) -> JSONResponse:
        """Modify session with provided data."""
        data = await request.json()
        for key, value in data.items():
            if value is None:
                request.session.pop(key, None)
            else:
                request.session[key] = value
        return JSONResponse({"session": dict(request.session)})

    """Create a test app with SessionMiddleware."""
    routes = [
        Route("/", homepage),
        Route("/set", set_session, methods=["POST"]),
        Route("/get", get_session),
        Route("/clear", clear_session_route),
        Route("/modify", modify_session, methods=["POST"]),
    ]
    kwargs = {"secret_key": "test-secret-key", **middleware_kwargs}
    middleware = [Middleware(SessionMiddleware, **kwargs)]
    return Starlette(routes=routes, middleware=middleware)


class TestSessionMiddleware:
    def test_session_creation(self) -> None:
        """Test that a session cookie is set on the first request."""
        app = create_test_app()
        client = TestClient(app)

        response = client.get("/")
        assert response.status_code == 200
        assert "session" in response.cookies
        assert response.text == "OK"

    def test_session_reading(self) -> None:
        """Test that session data can be read from the cookie on subsequent requests."""
        app = create_test_app()
        client = TestClient(app)

        # First request sets session
        response = client.get("/")
        assert response.status_code == 200

        # Second request should read the session
        response = client.get("/get")
        assert response.status_code == 200
        data = response.json()
        assert "visited" in data["session"]
        assert data["session"]["visited"] == 1

    def test_session_modification(self) -> None:
        """Test that session data can be modified and persisted across requests."""
        app = create_test_app()
        client = TestClient(app)

        response = client.post("/set", json={"user": "test_user", "role": "admin"})
        assert response.status_code == 200
        assert response.json()["session"]["user"] == "test_user"

        response = client.get("/get")
        assert response.status_code == 200
        data = response.json()
        assert data["session"]["user"] == "test_user"
        assert data["session"]["role"] == "admin"

    def test_session_clearing(self) -> None:
        """Test that clearing the session removes the cookie."""
        app = create_test_app()
        client = TestClient(app)

        response = client.post("/set", json={"user": "test_user"})
        assert response.status_code == 200

        # Clear session
        response = client.get("/clear")
        assert response.status_code == 200

        # Verify session is cleared
        response = client.get("/get")
        assert response.status_code == 200
        data = response.json()
        assert data["session"] == {}

    def test_session_max_age(self) -> None:
        """Test that the Max-Age attribute is set correctly."""
        max_age = 3600
        app = create_test_app(max_age=max_age)
        client = TestClient(app)

        response = client.get("/")
        assert response.status_code == 200

        set_cookie_header = response.headers.get("set-cookie", "")
        assert f"Max-Age={max_age}" in set_cookie_header

    def test_session_https_only(self) -> None:
        """Test that the secure flag is set when https_only is True."""
        app = create_test_app(https_only=True)
        client = TestClient(app)

        response = client.get("/")
        assert response.status_code == 200

        set_cookie_header = response.headers.get("set-cookie", "")
        assert "secure" in set_cookie_header

    def test_session_same_site(self) -> None:
        """Test that the samesite attribute is set correctly."""
        app = create_test_app(same_site="strict")
        client = TestClient(app)

        response = client.get("/")
        assert response.status_code == 200

        set_cookie_header = response.headers.get("set-cookie", "")
        assert "samesite=strict" in set_cookie_header

    def test_session_expiration_past(self) -> None:
        """Test that an expired session is not loaded and a new one is created."""
        app = create_test_app()
        client = TestClient(app)

        # Build a token that expired one hour ago
        expired = int(time.time()) - 3600
        payload = {"user": "test_user", "exp": expired}
        key = OctKey.import_key("test-secret-key")
        token = jwt.encode({"alg": "HS256"}, payload, key=key)

        response = client.get("/get", cookies={"session": token})
        assert response.status_code == 200
        # middleware must reject the expired token → empty session
        assert response.json()["session"] == {}

    def test_session_not_before_future(self) -> None:
        """Test that a session with a 'not before' claim in the future is ignored."""
        app = create_test_app()
        client = TestClient(app)

        # Build a token that is not valid until tomorrow
        nbf = int(time.time()) + 86400
        payload = {"user": "test_user", "nbf": nbf}
        key = OctKey.import_key("test-secret-key")
        token = jwt.encode({"alg": "HS256"}, payload, key=key)

        response = client.get("/get", cookies={"session": token})
        assert response.status_code == 200
        # middleware must reject the future token → empty session
        assert response.json()["session"] == {}

    def test_session_bad_signature(self) -> None:
        """Test that a session with a bad signature is ignored and a new session is created."""
        app = create_test_app()
        client = TestClient(app)

        # Create a session
        response = client.post("/set", json={"user": "test_user"})
        assert response.status_code == 200

        # Tamper with the cookie (simulate bad signature)
        tampered_cookie = response.cookies["session"][:-10] + "tampereddata"
        response = client.get("/get", cookies={"session": tampered_cookie})
        assert response.status_code == 200
        data = response.json()

        # Should have a new empty session, not the tampered one
        assert "user" not in data["session"]

    def test_session_cookie_name(self) -> None:
        """Test that custom session cookie name works."""
        custom_cookie_name = "my_session"
        app = create_test_app(session_cookie=custom_cookie_name)
        client = TestClient(app)

        response = client.get("/")
        assert response.status_code == 200
        assert custom_cookie_name in response.cookies
        assert "session" not in response.cookies

    def test_session_jwt_algorithm(self) -> None:
        """Test that custom JWT algorithm works."""
        app = create_test_app(jwt_alg="HS256")
        client = TestClient(app)

        response = client.post("/set", json={"user": "test_user"})
        assert response.status_code == 200

        token = response.cookies["session"]
        decoded = jwt.decode(
            token,
            key=OctKey.import_key("test-secret-key"),
            algorithms=["HS256"],
        )
        assert decoded.header["alg"] == "HS256"

    def test_session_data_modification(self) -> None:
        """Test that session data can be modified correctly."""
        app = create_test_app()
        client = TestClient(app)

        # Set initial data
        response = client.post("/set", json={"counter": 1, "name": "Alice"})
        assert response.status_code == 200

        # Modify data
        response = client.post("/modify", json={"counter": 2, "name": None})
        assert response.status_code == 200
        data = response.json()
        assert data["session"]["counter"] == 2
        assert "name" not in data["session"]  # Should be removed

        # Verify changes persist
        response = client.get("/get")
        assert response.status_code == 200
        data = response.json()
        assert data["session"]["counter"] == 2
        assert "name" not in data["session"]

    def test_session_empty_on_first_visit(self) -> None:
        """Test that session is empty on first visit."""
        app = create_test_app()
        client = TestClient(app)

        response = client.get("/get")
        assert response.status_code == 200
        data = response.json()
        assert data["session"] == {}

    def test_session_visits_counter(self) -> None:
        """Test that the visits counter increments correctly."""
        app = create_test_app()
        client = TestClient(app)

        # First visit
        response = client.get("/")
        assert response.status_code == 200

        response = client.get("/get")
        data = response.json()
        assert data["session"]["visited"] == 1

        # Second visit
        response = client.get("/")
        assert response.status_code == 200

        response = client.get("/get")
        data = response.json()
        assert data["session"]["visited"] == 2

    def test_session_with_special_characters(self) -> None:
        """Test that session data with special characters works correctly."""
        app = create_test_app()
        client = TestClient(app)

        special_data = {
            "emoji": "🚀",
            "unicode": "你好世界",
            "special": "test@#$%^&*()",
            "nested": {"list": [1, 2, 3], "dict": {"a": 1}},
        }

        response = client.post("/set", json=special_data)
        assert response.status_code == 200

        response = client.get("/get")
        assert response.status_code == 200

        data = response.json()
        assert data["session"]["emoji"] == special_data["emoji"]
        assert data["session"]["unicode"] == special_data["unicode"]
        assert data["session"]["special"] == special_data["special"]
        assert data["session"]["nested"] == special_data["nested"]


def test_full_session_lifecycle():
    """Test the complete lifecycle of a session."""
    app = create_test_app(max_age=3600)
    client = TestClient(app)

    # Start with no session
    response = client.get("/get")
    assert response.status_code == 200
    assert response.json()["session"] == {}

    # Create a session
    response = client.post("/set", json={"user": "test_user", "role": "user"})
    assert response.status_code == 200

    # Verify session persists
    response = client.get("/get")
    assert response.status_code == 200
    data = response.json()
    assert data["session"]["user"] == "test_user"
    assert data["session"]["role"] == "user"

    # Modify session
    response = client.post("/modify", json={"role": "admin"})
    assert response.status_code == 200

    # Verify modification
    response = client.get("/get")
    assert response.status_code == 200
    data = response.json()
    assert data["session"]["role"] == "admin"

    # Clear session
    response = client.get("/clear")
    assert response.status_code == 200

    # Verify session is cleared
    response = client.get("/get")
    assert response.status_code == 200
    assert response.json()["session"] == {}
