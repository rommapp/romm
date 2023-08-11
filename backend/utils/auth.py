from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
)
from starlette.requests import HTTPConnection
from starlette_csrf import CSRFMiddleware
from starlette.types import Receive, Scope, Send

from handler import dbh
from config import (
    ROMM_SECRET_KEY,
    ROMM_AUTH_ENABLED,
    ROMM_AUTH_USERNAME,
    ROMM_AUTH_PASSWORD,
)
from utils.cache import cache
from models.user import User, Role, FULL_SCOPES

ALGORITHM = "HS256"


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def authenticate_user(username: str, password: str):
    user = dbh.get_user(username)
    if not user:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def create_oauth_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, ROMM_SECRET_KEY, algorithm=ALGORITHM)


credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_active_user_from_token(token: str):
    try:
        payload = jwt.decode(token, ROMM_SECRET_KEY, algorithms=[ALGORITHM])
    except (JWTError):
        raise credentials_exception

    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    user = dbh.get_user(username)
    if user is None:
        raise credentials_exception

    if user.disabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user"
        )

    return user, payload


async def get_current_active_user_from_session(conn: HTTPConnection):
    # Check if session key already stored in cache
    session_id = conn.session.get("session_id")
    if not session_id:
        return None

    username = cache.get(f"romm:{session_id}")
    if not username:
        return None

    # Key exists therefore user is authenticated
    user = dbh.get_user(username)
    if user is None:
        raise credentials_exception

    if user.disabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
        )

    return user


class BasicAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn: HTTPConnection):
        if not ROMM_AUTH_ENABLED:
            return (AuthCredentials(FULL_SCOPES), None)

        # Check if session key already stored in cache
        user = await get_current_active_user_from_session(conn)
        if user:
            return (AuthCredentials(user.oauth_scopes), user)

        # Check if Authorization header exists
        if "Authorization" not in conn.headers:
            return None

        # Returns if Authorization header is not Bearer
        scheme, token = conn.headers["Authorization"].split()
        if scheme.lower() != "bearer":
            return None

        user, payload = await get_current_active_user_from_token(token)

        # Only access tokens can request resources
        if payload.get("type") == "access":
            return (AuthCredentials(user.oauth_scopes), user)

        return None


class CustomCSRFMiddleware(CSRFMiddleware):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        await super().__call__(scope, receive, send)


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
