import enum
from datetime import datetime, timedelta, timezone
from typing import Any, Final

import httpx
from config import OIDC_SERVER_APPLICATION_URL, ROMM_AUTH_SECRET_KEY
from exceptions.auth_exceptions import OAuthCredentialsException
from fastapi import HTTPException, status
from joserfc import jwt
from joserfc.errors import BadSignatureError
from joserfc.jwk import OctKey, RSAKey
from logger.logger import log
from passlib.context import CryptContext
from starlette.requests import HTTPConnection

ALGORITHM: Final = "HS256"
DEFAULT_OAUTH_TOKEN_EXPIRY: Final = timedelta(minutes=15)


class Scope(enum.StrEnum):
    ME_READ = "me.read"
    ME_WRITE = "me.write"
    ROMS_READ = "roms.read"
    ROMS_WRITE = "roms.write"
    ROMS_USER_READ = "roms.user.read"
    ROMS_USER_WRITE = "roms.user.write"
    PLATFORMS_READ = "platforms.read"
    PLATFORMS_WRITE = "platforms.write"
    ASSETS_READ = "assets.read"
    ASSETS_WRITE = "assets.write"
    FIRMWARE_READ = "firmware.read"
    FIRMWARE_WRITE = "firmware.write"
    COLLECTIONS_READ = "collections.read"
    COLLECTIONS_WRITE = "collections.write"
    USERS_READ = "users.read"
    USERS_WRITE = "users.write"
    TASKS_RUN = "tasks.run"


DEFAULT_SCOPES_MAP: Final = {
    Scope.ME_READ: "View your profile",
    Scope.ME_WRITE: "Modify your profile",
    Scope.ROMS_READ: "View ROMs",
    Scope.PLATFORMS_READ: "View platforms",
    Scope.ASSETS_READ: "View assets",
    Scope.ASSETS_WRITE: "Modify assets",
    Scope.FIRMWARE_READ: "View firmware",
    Scope.ROMS_USER_READ: "View user-rom properties",
    Scope.ROMS_USER_WRITE: "Modify user-rom properties",
    Scope.COLLECTIONS_READ: "View collections",
    Scope.COLLECTIONS_WRITE: "Modify collections",
}

WRITE_SCOPES_MAP: Final = {
    Scope.ROMS_WRITE: "Modify ROMs",
    Scope.PLATFORMS_WRITE: "Modify platforms",
    Scope.FIRMWARE_WRITE: "Modify firmware",
}

FULL_SCOPES_MAP: Final = {
    Scope.USERS_READ: "View users",
    Scope.USERS_WRITE: "Modify users",
    Scope.TASKS_RUN: "Run tasks",
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
        if user is None or not user.enabled:
            conn.session.clear()
            log.error(
                "User '%s' %s",
                username,
                "not found" if user is None else "not enabled",
            )
            return None

        return user

class OAuthHandler:
    def __init__(self) -> None:
        pass

    def create_oauth_token(
        self, data: dict, expires_delta: timedelta = DEFAULT_OAUTH_TOKEN_EXPIRY
    ) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + expires_delta
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


class OpenIDHandler:
    def __init__(self) -> None:
        jwks_url = f"{OIDC_SERVER_APPLICATION_URL}/jwks/"
        with httpx.Client() as httpx_client:
            try:
                response = httpx_client.get(jwks_url, timeout=120)
                key = response.json()["keys"][0]
                self.rsa_key = RSAKey.import_key(key)
            except httpx.HTTPStatusError as exc:
                raise HTTPException(
                    status_code=exc.response.status_code,
                    detail=exc.response.text,
                ) from exc

    async def get_current_active_user_from_openid_token(self, token: Any):
        from handler.database import db_user_handler

        id_token = token.get("id_token")

        try:
            payload = jwt.decode(id_token, self.rsa_key, algorithms=["RS256"])
        except (BadSignatureError, ValueError) as exc:
            raise OAuthCredentialsException from exc

        iss = payload.claims.get("iss")
        if OIDC_SERVER_APPLICATION_URL not in str(iss):
            raise OAuthCredentialsException

        username = payload.claims.get("preferred_username")
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
