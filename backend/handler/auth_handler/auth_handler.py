from datetime import datetime, timedelta

from config import (
    ROMM_AUTH_ENABLED,
    ROMM_AUTH_PASSWORD,
    ROMM_AUTH_SECRET_KEY,
    ROMM_AUTH_USERNAME,
)
from exceptions.auth_exceptions import OAuthCredentialsException
from fastapi import HTTPException, Request, status
from handler.auth_handler import ALGORITHM, DEFAULT_OAUTH_TOKEN_EXPIRY
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
from starlette.requests import HTTPConnection
from handler.redis_handler import cache


class AuthHandler:
    def __init__(self) -> None:
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def _verify_password(self, plain_password, hashed_password):
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password):
        return self.pwd_context.hash(password)

    @staticmethod
    def clear_session(req: HTTPConnection | Request):
        session_id = req.session.get("session_id")
        if session_id:
            redish.cache.delete(f"romm:{session_id}")  # type: ignore[attr-defined]
            req.session["session_id"] = None

    def authenticate_user(self, username: str, password: str):
        from handler import dbh

        user = dbh.get_user_by_username(username)
        if not user:
            return None

        if not self._verify_password(password, user.hashed_password):
            return None

        return user

    async def get_current_active_user_from_session(self, conn: HTTPConnection):
        from handler import dbh

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
            self.clear_session(conn)

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not found",
            )

        if not user.enabled:
            self.clear_session(conn)

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
            )

        return user

    def create_default_admin_user(self):
        from handler import dbh
        from models.user import Role, User

        if not ROMM_AUTH_ENABLED:
            return

        try:
            dbh.add_user(
                User(
                    username=ROMM_AUTH_USERNAME,
                    hashed_password=self.get_password_hash(ROMM_AUTH_PASSWORD),
                    role=Role.ADMIN,
                )
            )
        except IntegrityError:
            pass


class OAuthHandler:
    def __init__(self) -> None:
        pass

    def create_oauth_token(data: dict, expires_delta: timedelta | None = None):
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=DEFAULT_OAUTH_TOKEN_EXPIRY)

        to_encode.update({"exp": expire})

        return jwt.encode(to_encode, ROMM_AUTH_SECRET_KEY, algorithm=ALGORITHM)

    async def get_current_active_user_from_bearer_token(token: str):
        from handler import dbh

        try:
            payload = jwt.decode(token, ROMM_AUTH_SECRET_KEY, algorithms=[ALGORITHM])
        except JWTError:
            raise OAuthCredentialsException

        username = payload.get("sub")
        if username is None:
            raise OAuthCredentialsException

        user = dbh.get_user_by_username(username)
        if user is None:
            raise OAuthCredentialsException

        if not user.enabled:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user"
            )

        return user, payload
