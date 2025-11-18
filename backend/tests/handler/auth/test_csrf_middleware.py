import re

from itsdangerous import URLSafeSerializer
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from config import ROMM_AUTH_SECRET_KEY
from handler.auth.constants import ALGORITHM
from handler.auth.hybrid_auth import HybridAuthBackend
from handler.auth.middleware.csrf_middleware import CSRFMiddleware
from handler.auth.middleware.session_middleware import SessionMiddleware


# Test app factory                                                            #
def create_test_app(**csrf_kwargs) -> Starlette:
    """Return a Starlette app wired with CSRFMiddleware."""

    async def get_handler(request: Request) -> PlainTextResponse:
        return PlainTextResponse("OK")

    async def post_handler(request: Request) -> JSONResponse:
        return JSONResponse({"status": "success"})

    async def post_echo(request: Request) -> JSONResponse:
        """Return the CSRF token that was sent."""
        token = request.headers.get(csrf_kwargs.get("header_name", "x-csrftoken"))
        return JSONResponse({"token": token})

    routes = [
        Route("/get", get_handler, methods=["GET"]),
        Route("/post", post_handler, methods=["POST"]),
        Route("/echo", post_echo, methods=["POST"]),
    ]
    middleware = [
        Middleware(CSRFMiddleware, secret="test-secret", **csrf_kwargs),
        Middleware(AuthenticationMiddleware, backend=HybridAuthBackend()),
        Middleware(
            SessionMiddleware,
            secret_key=ROMM_AUTH_SECRET_KEY,
            session_cookie="romm_session",
            same_site="strict",
            https_only=False,
            jwt_alg=ALGORITHM,
        ),
    ]
    return Starlette(routes=routes, middleware=middleware)


class TestCSRFMiddleware:
    def test_csrf_cookie_set_on_first_get(self) -> None:
        """A GET request should set the CSRF cookie if none exists."""
        app = create_test_app()
        client = TestClient(app)

        response = client.get("/get")
        assert response.status_code == 200
        assert "csrftoken" in response.cookies

    def test_post_with_valid_token_succeeds(self) -> None:
        """POST with correct CSRF header should pass."""
        app = create_test_app()
        client = TestClient(app)

        # Obtain cookie
        resp = client.get("/get")
        cookie = resp.cookies["csrftoken"]

        # Post with token
        resp = client.post("/post", headers={"x-csrftoken": cookie})
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_post_without_cookie_fails(self) -> None:
        """POST without CSRF cookie should fail."""
        app = create_test_app()
        client = TestClient(app)

        resp = client.post("/post")
        assert resp.status_code == 403
        assert "CSRF token verification failed" in resp.text

    def test_post_without_header_fails(self) -> None:
        """POST without CSRF header should fail."""
        app = create_test_app()
        client = TestClient(app)

        # Obtain cookie but don't send header
        client.get("/get")
        resp = client.post("/post")
        assert resp.status_code == 403

    def test_post_with_bad_signature_fails(self) -> None:
        """POST with tampered token should fail."""
        app = create_test_app()
        client = TestClient(app)

        client.get("/get")
        bad_token = "tampered-token"
        resp = client.post("/post", headers={"x-csrftoken": bad_token})
        assert resp.status_code == 403

    def test_safe_methods_bypass_csrf(self) -> None:
        """GET/HEAD/OPTIONS/TRACE should never require CSRF."""
        app = create_test_app()
        client = TestClient(app)

        for method in ("GET", "HEAD", "OPTIONS", "TRACE"):
            resp = client.request(method, "/post")
            assert resp.status_code == 200

    def test_custom_header_name(self) -> None:
        """Middleware should read the token from the configured header."""
        header_name = "x-xsrf-token"
        app = create_test_app(header_name=header_name)
        client = TestClient(app)

        cookie_resp = client.get("/get")
        token = cookie_resp.cookies["csrftoken"]

        # Send with custom header
        resp = client.post("/echo", headers={header_name: token})
        assert resp.status_code == 200
        assert resp.json()["token"] == token

    def test_custom_cookie_name(self) -> None:
        """Middleware should use the configured cookie name."""
        cookie_name = "my_token"
        app = create_test_app(cookie_name=cookie_name)
        client = TestClient(app)

        resp = client.get("/get")
        assert cookie_name in resp.cookies

    def test_cookie_attributes(self) -> None:
        """Verify Secure, HttpOnly, SameSite, Path, Domain attributes."""
        app = create_test_app(
            cookie_secure=True,
            cookie_httponly=True,
            cookie_samesite="strict",
            cookie_path="/app",
            cookie_domain=".example.com",
        )
        client = TestClient(app)

        resp = client.get("/get")
        set_cookie = resp.headers["set-cookie"]
        assert "secure" in set_cookie
        assert "httponly" in set_cookie
        assert "samesite=strict" in set_cookie
        assert "path=/app" in set_cookie
        assert "domain=.example.com" in set_cookie

    def test_exempt_urls(self) -> None:
        """POST to exempt URLs should not require CSRF."""
        app = create_test_app(exempt_urls=[re.compile(r"^/post$")])
        client = TestClient(app)

        # No cookie/header needed
        resp = client.post("/post")
        assert resp.status_code == 200

    def test_required_urls(self) -> None:
        """POST to required URLs should always require CSRF even for safe methods."""
        app = create_test_app(required_urls=[re.compile(r"^/get$")], safe_methods=set())
        client = TestClient(app)

        # GET now requires token
        resp = client.get("/get")
        assert resp.status_code == 403

    def test_sensitive_cookies(self) -> None:
        """If no sensitive cookies exist, CSRF is not enforced."""
        app = create_test_app(sensitive_cookies={"session"})
        client = TestClient(app)

        # No sensitive cookie → POST allowed
        resp = client.post("/post")
        assert resp.status_code == 200

        # Add sensitive cookie → POST blocked
        client.cookies.set("session", "abc123")
        resp = client.post("/post")
        assert resp.status_code == 403

    # Bypass rules                                                       #
    def test_bearer_auth_bypass(self) -> None:
        """Requests with Bearer/Basic Authorization header bypass CSRF."""
        app = create_test_app()
        client = TestClient(app)

        resp = client.post("/post", headers={"Authorization": "Bearer token"})
        assert resp.status_code == 200

    def test_non_http_scope_bypass(self) -> None:
        """WebSocket (or other non-HTTP) scopes should pass through."""
        # Manual ASGI call; TestClient doesn't expose WebSocket easily
        scope = {"type": "websocket", "path": "/ws", "headers": []}
        receive = lambda: {}  # noqa: E731
        send = lambda msg: None  # noqa: E731

        async def dummy_app(scope, receive, send):
            await send({"type": "websocket.accept"})

        middleware = CSRFMiddleware(dummy_app, secret="test")
        import asyncio

        asyncio.run(middleware(scope, receive, send))  # should not raise

    def test_token_generation_and_validation(self) -> None:
        """Ensure tokens are signed and validated correctly."""
        app = create_test_app()
        client = TestClient(app)

        # Extract cookie
        resp = client.get("/get")
        cookie = resp.cookies["csrftoken"]

        # Verify signature
        serializer = URLSafeSerializer("test-secret", "csrftoken")
        payload = serializer.loads(cookie)
        assert "token" in payload
        assert "user_id" in payload

        # Send same token back
        resp = client.post("/echo", headers={"x-csrftoken": cookie})
        assert resp.status_code == 200
        assert resp.json()["token"] == cookie

    def test_user_id_mismatch_fails(self) -> None:
        """Tokens issued for one user must not validate for another."""
        # We simulate two users by calling _generate_csrf_token with different IDs
        mw = CSRFMiddleware(app=lambda s, r, se: None, secret="test")
        user1_token = mw._generate_csrf_token(user_id=1)
        mw._generate_csrf_token(user_id=2)

        # user1_token should not validate for user_id=2
        assert not mw._csrf_tokens_match(user1_token, user1_token, user_id=2)

    def test_bad_signature_returns_false(self) -> None:
        """_csrf_tokens_match should return False on BadSignature."""
        mw = CSRFMiddleware(app=lambda s, r, se: None, secret="test")
        ok = mw._csrf_tokens_match("bad-token", "bad-token", user_id=None)
        assert ok is False
