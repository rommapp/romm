import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from joserfc import jwt
from joserfc.errors import BadSignatureError, DecodeError
from joserfc.jwk import OctKey
from passlib.context import CryptContext
from starlette.requests import HTTPConnection

from config import (
    OIDC_CLAIM_ROLES,
    OIDC_ENABLED,
    OIDC_ROLE_ADMIN,
    OIDC_ROLE_EDITOR,
    OIDC_ROLE_VIEWER,
    ROMM_AUTH_SECRET_KEY,
    ROMM_BASE_URL,
)
from decorators.auth import oauth
from exceptions.auth_exceptions import OAuthCredentialsException, UserDisabledException
from handler.auth.constants import ALGORITHM, DEFAULT_OAUTH_TOKEN_EXPIRY, TokenPurpose
from handler.auth.middleware.redis_session_middleware import RedisSessionMiddleware
from handler.redis_handler import redis_client
from logger.formatter import CYAN
from logger.formatter import highlight as hl
from logger.logger import log

oct_key = OctKey.import_key(ROMM_AUTH_SECRET_KEY)


class AuthHandler:
    def __init__(self) -> None:
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.reset_passwd_token_expires_in_minutes = 10
        self.invite_link_token_expires_in_minutes = 10

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
                hl(username, color=CYAN),
                "not found" if user is None else "not enabled",
            )
            return None

        return user

    def generate_password_reset_token(self, user: Any) -> None:
        now = datetime.now(timezone.utc)

        jti = str(uuid.uuid4())

        to_encode = {
            "sub": user.username,
            "email": user.email,
            "type": TokenPurpose.RESET,
            "iat": int(now.timestamp()),
            "exp": int(
                (
                    now + timedelta(minutes=self.reset_passwd_token_expires_in_minutes)
                ).timestamp()
            ),
            "jti": jti,
        }
        token = jwt.encode(
            {"alg": ALGORITHM},
            to_encode,
            oct_key,
        )
        log.info(
            f"Reset password link requested for {hl(user.username, color=CYAN)}. Reset link: {hl(f'{ROMM_BASE_URL}/reset-password?token={token}')}"
        )
        redis_client.setex(
            f"reset-jti:{jti}", self.reset_passwd_token_expires_in_minutes * 60, "valid"
        )

    def verify_password_reset_token(self, token: str) -> Any:
        """Verify the password reset token.

        Args:
            token (str): The token to verify.

        Raises:
            HTTPException: If the token is invalid or expired.
            HTTPException: If the token is missing or malformed.
            HTTPException: If the user is not found.
            HTTPException: If the token is not for password reset.
        """
        from handler.database import db_user_handler

        try:
            payload = jwt.decode(token, oct_key, algorithms=[ALGORITHM])
        except (BadSignatureError, DecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid token") from exc

        if payload.claims.get("type") != TokenPurpose.RESET:
            raise HTTPException(status_code=400, detail="Invalid token purpose")

        username = payload.claims.get("sub")
        jti = payload.claims.get("jti")
        if not username or not jti:
            raise HTTPException(status_code=400, detail="Invalid token payload")

        # Check JTI in Redis
        redis_jti_key = f"reset-jti:{jti}"
        if not redis_client.exists(redis_jti_key):
            raise HTTPException(
                status_code=400, detail="This token has already been used or is invalid"
            )

        # Delete it to enforce one-time use
        redis_client.delete(redis_jti_key)

        user = db_user_handler.get_user_by_username(username)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        now = datetime.now(timezone.utc).timestamp()
        if now > payload.claims.get("exp", 0.0):
            raise HTTPException(status_code=400, detail="Token has expired")

        return user

    async def set_user_new_password(self, user: Any, new_password: str) -> None:
        """
        Set the new password for the user.
        Args:
            user (Any): The user object.
            new_password (str): The new password to set.
        """
        from handler.database import db_user_handler

        db_user_handler.update_user(
            user.id, {"hashed_password": self.get_password_hash(new_password)}
        )
        await RedisSessionMiddleware.clear_user_sessions(user.username)

    def generate_invite_link_token(self, user: Any, role: str) -> str:
        """
        Generate an invite link token for the user.
        Args:
            user (Any): The user object.
            role (str): The role of the user.
        Returns:
            str: The generated invite link token.
        """
        now = datetime.now(timezone.utc)

        jti = str(uuid.uuid4())

        to_encode = {
            "sub": user.username,
            "type": TokenPurpose.INVITE,
            "role": role.upper(),
            "iat": int(now.timestamp()),
            "exp": int(
                (
                    now + timedelta(minutes=self.invite_link_token_expires_in_minutes)
                ).timestamp()
            ),
            "jti": jti,
        }
        token = jwt.encode(
            {"alg": ALGORITHM},
            to_encode,
            oct_key,
        )
        invite_link = f"{ROMM_BASE_URL}/register?token={token}"
        log.info(
            f"Invite link created by {hl(user.username, color=CYAN)}: {hl(invite_link)}"
        )
        redis_client.setex(
            f"invite-jti:{jti}", self.invite_link_token_expires_in_minutes * 60, "valid"
        )
        return token

    def consume_invite_link_token(self, token: str) -> str:
        """
        Verify and consume the invite link token, which invalidates the token to prevent reuse.

        Args:
            token (str): The token to verify.

        Returns:
            str: The role associated with the token.
        """
        try:
            payload = jwt.decode(token, oct_key, algorithms=[ALGORITHM])
        except (BadSignatureError, DecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid token") from exc

        if payload.claims.get("type") != TokenPurpose.INVITE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token type.",
            )

        jti = payload.claims.get("jti")
        role = payload.claims.get("role", "USER").upper()
        if not jti or redis_client.get(f"invite-jti:{jti}") != b"valid":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invite token has already been used or is invalid.",
            )

        # Invalidate the token as soon as it's read
        redis_client.delete(f"invite-jti:{jti}")

        return role


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
            {"alg": ALGORITHM},
            to_encode,
            oct_key,
        )

    async def get_current_active_user_from_bearer_token(self, token: str):
        from handler.database import db_user_handler

        try:
            payload = jwt.decode(token, oct_key, algorithms=[ALGORITHM])
        except (BadSignatureError, DecodeError, ValueError) as exc:
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

        role = Role.VIEWER
        if OIDC_CLAIM_ROLES and OIDC_CLAIM_ROLES in userinfo:
            roles = userinfo[OIDC_CLAIM_ROLES] or []
            if OIDC_ROLE_ADMIN and OIDC_ROLE_ADMIN in roles:
                role = Role.ADMIN
            elif OIDC_ROLE_EDITOR and OIDC_ROLE_EDITOR in roles:
                role = Role.EDITOR
            elif OIDC_ROLE_VIEWER and (
                OIDC_ROLE_VIEWER in roles or OIDC_ROLE_VIEWER == "*"
            ):
                role = Role.VIEWER
            else:
                log.error("User has not been granted any roles for this application.")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User has not been granted any roles for this application.",
                )

        user = db_user_handler.get_user_by_email(email)
        if user is None:
            log.info(
                "User with email '%s' not found, creating new user",
                hl(email, color=CYAN),
            )
            new_user = User(
                username=preferred_username,
                hashed_password=str(uuid.uuid4()),
                email=email,
                enabled=True,
                role=role,
            )
            user = db_user_handler.add_user(new_user)
        elif OIDC_CLAIM_ROLES and user.role != role:
            user = db_user_handler.update_user(user.id, {"role": role})

        if not user.enabled:
            raise UserDisabledException

        log.info("User successfully authenticated: %s", hl(email, color=CYAN))
        return user, userinfo
