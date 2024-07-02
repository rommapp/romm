from datetime import datetime, timedelta
from typing import Final

from config import ROMM_AUTH_PASSWORD, ROMM_AUTH_SECRET_KEY, ROMM_AUTH_USERNAME
from exceptions.auth_exceptions import OAuthCredentialsException
from fastapi import HTTPException, status
from joserfc import jwt
from joserfc.errors import BadSignatureError
from joserfc.jwk import OctKey
from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
from starlette.requests import HTTPConnection

ALGORITHM: Final = "HS256"
DEFAULT_OAUTH_TOKEN_EXPIRY: Final = 15

DEFAULT_SCOPES_MAP: Final = {
    "me.read": "View your profile",
    "me.write": "Modify your profile",
    "roms.read": "View ROMs",
    "platforms.read": "View platforms",
    "assets.read": "View assets",
    "assets.write": "Modify assets",
    "firmware.read": "View firmware",
    "roms.user.read": "View user-rom properties",
    "roms.user.write": "Modify user-rom properties",
}

WRITE_SCOPES_MAP: Final = {
    "roms.write": "Modify ROMs",
    "platforms.write": "Modify platforms",
    "firmware.write": "Modify firmware",
}

FULL_SCOPES_MAP: Final = {
    "users.read": "View users",
    "users.write": "Modify users",
    "tasks.run": "Run tasks",
}

DEFAULT_SCOPES: Final = list(DEFAULT_SCOPES_MAP.keys())
WRITE_SCOPES: Final = DEFAULT_SCOPES + list(WRITE_SCOPES_MAP.keys())
FULL_SCOPES: Final = WRITE_SCOPES + list(FULL_SCOPES_MAP.keys())


class AuthHandler:
    def __init__(self) -> None:
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def verify_password(self, plain_password, hashed_password):
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password):
        return self.pwd_context.hash(password)

    def authenticate_user(self, username: str, password: str):
        from handler.database import db_user_handler

        user = db_user_handler.get_user_by_username(username)
        if not user:
            return None

        if not self.verify_password(password, user.hashed_password):
            return None

        return user

    async def get_current_active_user_from_session(self, conn: HTTPConnection):
        from handler.database import db_user_handler

        issuer = conn.session.get("iss")
        if not issuer or issuer != "romm:auth":
            return None

        username = conn.session.get("sub")
        if not username:
            return None

        # Key exists therefore user is probably authenticated
        user = db_user_handler.get_user_by_username(username)
        if user is None:
            conn.session = {}

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not found",
            )

        if not user.enabled:
            conn.session = {}

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
            )

        return user

    def create_default_admin_user(self):
        from handler.database import db_user_handler
        from models.user import Role, User

        try:
            db_user_handler.add_user(
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

    def create_oauth_token(self, data: dict, expires_delta: timedelta | None = None):
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=DEFAULT_OAUTH_TOKEN_EXPIRY)

        to_encode.update({"exp": expire})

        return jwt.encode(
            {"alg": ALGORITHM}, to_encode, OctKey.import_key(ROMM_AUTH_SECRET_KEY)
        )

    async def get_current_active_user_from_bearer_token(self, token: str):
        from handler.database import db_user_handler

        try:
            payload = jwt.decode(token, OctKey.import_key(ROMM_AUTH_SECRET_KEY))
        except (BadSignatureError, ValueError) as exc:
            raise OAuthCredentialsException from exc

        issuer = payload.claims.get("iss")
        if not issuer or issuer != "romm:oauth":
            return None

        username = payload.claims.get("sub")
        if username is None:
            raise OAuthCredentialsException

        user = db_user_handler.get_user_by_username(username)
        if user is None:
            raise OAuthCredentialsException

        if not user.enabled:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user"
            )

        return user, payload.claims
