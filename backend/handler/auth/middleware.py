import time
from collections import namedtuple

from joserfc import jwt
from joserfc.errors import BadSignatureError
from joserfc.jwk import OctKey
from starlette.datastructures import MutableHeaders, Secret
from starlette.requests import HTTPConnection, Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from starlette_csrf.middleware import CSRFMiddleware

from config import SESSION_MAX_AGE_SECONDS


class CustomCSRFMiddleware(CSRFMiddleware):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Skip CSRF check if not an HTTP request, like websockets
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return None

        request = Request(scope, receive)

        # Skip CSRF check if Authorization header is present
        auth_scheme = request.headers.get("Authorization", "").split(" ", 1)[0].lower()
        if auth_scheme == "bearer" or auth_scheme == "basic":
            await self.app(scope, receive, send)
            return None

        await super().__call__(scope, receive, send)


SecretKey = namedtuple("SecretKey", ("encode", "decode"))


class SessionMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        secret_key: str | Secret | SecretKey,
        session_cookie: str = "session",
        max_age: int = SESSION_MAX_AGE_SECONDS,
        same_site: str = "lax",
        https_only: bool = False,
        jwt_alg: str = "HS256",
    ) -> None:
        self.app = app
        self.jwt_alg = jwt_alg

        if not isinstance(secret_key, SecretKey):
            self.jwt_secret = SecretKey(Secret(str(secret_key)), None)
        else:
            self.jwt_secret = secret_key

        # check crypto setup so we bail out if needed
        _jwt = jwt.encode(
            {"alg": jwt_alg},
            {"1": 2},
            key=OctKey.import_key(str(self.jwt_secret.encode)),
        )
        token = jwt.decode(
            _jwt,
            key=OctKey.import_key(
                str(
                    self.jwt_secret.decode
                    if self.jwt_secret.decode
                    else self.jwt_secret.encode
                )
            ),
            algorithms=[self.jwt_alg],
        )
        if token.claims != {"1": 2} or token.header != {"typ": "JWT", "alg": jwt_alg}:
            raise ValueError(
                "Invalid crypto setup, check your secret key and algorithm configuration"
            )

        self.session_cookie = session_cookie
        self.max_age = max_age
        self.security_flags = "httponly; samesite=" + same_site
        if https_only:  # Secure flag can be used with HTTPS only
            self.security_flags += "; secure"

    def _validate_jwt_payload(self, jwt_payload: jwt.Token):
        if not isinstance(jwt_payload.claims, dict):
            return {}

        # The "exp" (expiration time) claim identifies the expiration time on
        # or after which the JWT MUST NOT be accepted for processing.
        if "exp" in jwt_payload.claims and jwt_payload.claims["exp"] < int(time.time()):
            return {}

        # The "nbf" (not before) claim identifies the time before which the JWT
        # MUST NOT be accepted for processing.
        if "nbf" in jwt_payload.claims and jwt_payload.claims["nbf"] > int(time.time()):
            return {}

        return jwt_payload.claims

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):  # pragma: no cover
            await self.app(scope, receive, send)
            return None

        connection = HTTPConnection(scope)
        initial_session_was_empty = True

        if self.session_cookie in connection.cookies:
            data = connection.cookies[self.session_cookie].encode("utf-8")
            try:
                jwt_payload = jwt.decode(
                    data,
                    key=OctKey.import_key(
                        str(
                            self.jwt_secret.decode
                            if self.jwt_secret.decode
                            else self.jwt_secret.encode
                        )
                    ),
                    algorithms=[self.jwt_alg],
                )

                jwt_claims = self._validate_jwt_payload(jwt_payload)
                scope["session"] = jwt_claims
                initial_session_was_empty = False

            except BadSignatureError:
                scope["session"] = {}
        else:
            scope["session"] = {}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                if scope["session"]:
                    if "exp" not in scope["session"]:
                        scope["session"]["exp"] = int(time.time()) + self.max_age

                    data = jwt.encode(
                        {"alg": self.jwt_alg},
                        scope["session"],
                        key=OctKey.import_key(str(self.jwt_secret.encode)),
                    )

                    headers = MutableHeaders(scope=message)
                    header_value = "%s=%s; path=/; Max-Age=%d; %s" % (
                        self.session_cookie,
                        data,
                        self.max_age,
                        self.security_flags,
                    )
                    headers.append("Set-Cookie", header_value)
                elif not initial_session_was_empty:
                    # The session has been cleared.
                    headers = MutableHeaders(scope=message)
                    header_value = "{}={}; {}".format(
                        self.session_cookie,
                        "null; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT;",
                        self.security_flags,
                    )
                    headers.append("Set-Cookie", header_value)
            await send(message)

        await self.app(scope, receive, send_wrapper)
