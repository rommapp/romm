from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status, Request
from fastapi.security.http import HTTPBasic
from passlib.context import CryptContext
from starlette.requests import HTTPConnection
from starlette_csrf.middleware import CSRFMiddleware
from starlette.types import Receive, Scope, Send
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
)

from handler import dbh
from utils.cache import cache
from models.user import User, Role
from config import (
    ROMM_AUTH_ENABLED,
    ROMM_AUTH_USERNAME,
    ROMM_AUTH_PASSWORD,
)

from .oauth import (
    FULL_SCOPES,
    get_current_active_user_from_bearer_token,
)


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def authenticate_user(username: str, password: str):
    user = dbh.get_user_by_username(username)
    if not user:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user


def clear_session(req: HTTPConnection | Request):
    session_id = req.session.get("session_id")
    if session_id:
        cache.delete(f"romm:{session_id}")  # type: ignore[attr-defined]
        req.session["session_id"] = None


async def get_current_active_user_from_session(conn: HTTPConnection):
    # Check if session key already stored in cache
    session_id = conn.session.get("session_id")
    if not session_id:
        return None

    username = cache.get(f"romm:{session_id}")  # type: ignore[attr-defined]
    if not username:
        return None

    # Key exists therefore user is probably authenticated
    user = dbh.get_user_by_username(username)
    if user is None:
        clear_session(conn)

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not found",
        )

    if not user.enabled:
        clear_session(conn)

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
        )

    return user


def create_default_admin_user():
    if not ROMM_AUTH_ENABLED:
        return

    try:
        dbh.add_user(
            User(
                username=ROMM_AUTH_USERNAME,
                hashed_password=get_password_hash(ROMM_AUTH_PASSWORD),
                role=Role.ADMIN,
            )
        )
    except IntegrityError:
        pass


class HybridAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn: HTTPConnection):
        if not ROMM_AUTH_ENABLED:
            return (AuthCredentials(FULL_SCOPES), None)

        # Check if session key already stored in cache
        user = await get_current_active_user_from_session(conn)
        if user:
            return (AuthCredentials(user.oauth_scopes), user)

        # Check if Authorization header exists
        if "Authorization" not in conn.headers:
            return (AuthCredentials([]), None)

        scheme, token = conn.headers["Authorization"].split()

        # Check if basic auth header is valid
        if scheme.lower() == "basic":
            credentials = await HTTPBasic().__call__(conn)  # type: ignore[arg-type]
            if not credentials:
                return (AuthCredentials([]), None)

            user = authenticate_user(credentials.username, credentials.password)
            if user is None:
                return (AuthCredentials([]), None)

            return (AuthCredentials(user.oauth_scopes), user)

        # Check if bearer auth header is valid
        if scheme.lower() == "bearer":
            user, payload = await get_current_active_user_from_bearer_token(token)

            # Only access tokens can request resources
            if payload.get("type") != "access":
                return (AuthCredentials([]), None)

            # Only grant access to resources with overlapping scopes
            token_scopes = set(list(payload.get("scopes").split(" ")))
            overlapping_scopes = list(token_scopes & set(user.oauth_scopes))

            return (AuthCredentials(overlapping_scopes), user)

        return (AuthCredentials([]), None)


class CustomCSRFMiddleware(CSRFMiddleware):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        await super().__call__(scope, receive, send)
