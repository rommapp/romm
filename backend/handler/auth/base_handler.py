import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from config import OIDC_ENABLED, ROMM_AUTH_SECRET_KEY
from decorators.auth import oauth
from exceptions.auth_exceptions import OAuthCredentialsException, UserDisabledException
from fastapi import HTTPException, status
from handler.auth.constants import ALGORITHM, DEFAULT_OAUTH_TOKEN_EXPIRY
from joserfc import jwt
from joserfc.errors import BadSignatureError
from joserfc.jwk import OctKey
from logger.logger import log
from passlib.context import CryptContext
from starlette.requests import HTTPConnection


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


class OpenIDHandler:
    async def get_current_active_user_from_openid_token(self, token: Any):
        from handler.database import db_user_handler
        from models.user import Role, User

        if not OIDC_ENABLED:
            return None, None

        userinfo = token.get("userinfo")
        if userinfo is None:
            log.error("Userinfo is missing from token.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Userinfo is missing from token.",
            )

        email = userinfo.get("email")
        if email is None:
            log.error("Email is missing from token.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is missing from token.",
            )

        metadata = await oauth.openid.load_server_metadata()
        claims_supported = metadata.get("claims_supported")
        is_email_verified = userinfo.get("email_verified", None)

        # Fail if email is explicitly unverified, or `email_verified` is a supported claim and
        # email is not explicitly verified.
        if is_email_verified is False or (
            claims_supported
            and "email_verified" in claims_supported
            and is_email_verified is not True
        ):
            log.error("Email is not verified.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is not verified.",
            )

        preferred_username = userinfo.get("preferred_username")

        user = db_user_handler.get_user_by_email(email)
        if user is None:
            log.info("User with email '%s' not found, creating new user", email)
            new_user = User(
                username=preferred_username,
                hashed_password=str(uuid.uuid4()),
                email=email,
                enabled=True,
                role=Role.VIEWER,
            )
            user = db_user_handler.add_user(new_user)

        if not user.enabled:
            raise UserDisabledException

        log.info("User successfully authenticated: %s", email)
        return user, userinfo
