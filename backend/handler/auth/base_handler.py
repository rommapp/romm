import asyncio
import enum
from datetime import datetime, timedelta, timezone
from typing import Any, Final, Optional

import httpx
from config import OIDC_ENABLED, OIDC_SERVER_APPLICATION_URL, ROMM_AUTH_SECRET_KEY
from exceptions.auth_exceptions import OAuthCredentialsException, UserDisabledException
from fastapi import HTTPException, status
from joserfc import jwt
from joserfc.errors import BadSignatureError, ExpiredTokenError, InvalidPayloadError
from joserfc.jwk import OctKey, RSAKey
from logger.logger import log
from passlib.context import CryptContext
from starlette.requests import HTTPConnection
from utils.context import ctx_httpx_client

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
            return None, None

        username = payload.claims.get("sub")
        if username is None:
            raise OAuthCredentialsException

        user = db_user_handler.get_user_by_username(username)
        if user is None:
            raise OAuthCredentialsException

        if not user.enabled:
            raise UserDisabledException

        return user, payload.claims


class RSAKeyNotFoundError(Exception): ...


class OpenIDHandler:
    RSA_ALGORITHM = "RS256"

    def __init__(self) -> None:
        self._rsa_key: Optional[RSAKey] = None
        self._rsa_key_lock = asyncio.Lock()

    async def _fetch_rsa_key(self) -> RSAKey:
        """
        Fetch the public key from the OIDC server
        JWKS (JSON Web Key Sets) response is a JSON object with a keys array
        """
        jwks_url = f"{OIDC_SERVER_APPLICATION_URL}/jwks/"
        log.debug("Fetching JWKS from %s", jwks_url)

        httpx_client = ctx_httpx_client.get()
        try:
            response = await httpx_client.get(jwks_url, timeout=120)
            response.raise_for_status()
            keys = response.json().get("keys", [])
            if not keys:
                raise RSAKeyNotFoundError("No RSA keys found in JWKS response.")

            return RSAKey.import_key(keys[0])
        except (httpx.RequestError, KeyError, RSAKeyNotFoundError) as exc:
            log.error("Unable to fetch RSA public key: %s", str(exc))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to fetch RSA public key",
            ) from exc

    async def get_rsa_key(self) -> RSAKey:
        """
        Retrieves the cached RSA public key, or fetches it if not already cached.
        """
        if not self._rsa_key:
            async with self._rsa_key_lock:
                if not self._rsa_key:  # Double-check in case of concurrent calls
                    self._rsa_key = await self._fetch_rsa_key()
        return self._rsa_key

    async def validate_token(self, token: str) -> jwt.Token:
        """
        Validates a JWT token using the RSA public key.
        """
        try:
            rsa_key = await self.get_rsa_key()
            return jwt.decode(token, rsa_key, algorithms=[self.RSA_ALGORITHM])
        except (BadSignatureError, ExpiredTokenError, InvalidPayloadError) as exc:
            log.error("Token validation failed: %s", str(exc))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            ) from exc

    async def get_current_active_user_from_openid_token(self, token: Any):
        from handler.database import db_user_handler

        if not OIDC_ENABLED:
            return None, None

        id_token = token.get("id_token")
        if not id_token:
            log.error("ID Token is missing from token.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ID Token is missing from token.",
            )

        payload = await self.validate_token(id_token)

        iss = payload.claims.get("iss")
        if not iss or OIDC_SERVER_APPLICATION_URL not in str(iss):
            log.error("Invalid issuer in token: %s", iss)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid issuer in token.",
            )

        email = payload.claims.get("email")
        if email is None:
            log.error("Email is missing from token.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is missing from token.",
            )

        user = db_user_handler.get_user_by_email(email)
        if user is None:
            log.error("User with email '%s' not found", email)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        if not user.enabled:
            raise UserDisabledException

        log.info("User successfully authenticated: %s", email)
        return user, payload.claims
