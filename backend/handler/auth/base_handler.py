import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from joserfc import jwt
from joserfc.errors import BadSignatureError, DecodeError
from joserfc.jwk import OctKey
from passlib.context import CryptContext
from redis.exceptions import RedisError
from starlette.requests import HTTPConnection

from config import (
    EMAIL_ENABLED,
    INVITE_TOKEN_EXPIRY_SECONDS,
    OIDC_ALLOW_REGISTRATION,
    OIDC_CLAIM_ROLES,
    OIDC_ENABLED,
    OIDC_ROLE_ADMIN,
    OIDC_ROLE_EDITOR,
    OIDC_ROLE_VIEWER,
    OIDC_USERNAME_ATTRIBUTE,
    ROMM_AUTH_SECRET_KEY,
    ROMM_BASE_URL,
)
from decorators.auth import oauth
from exceptions.auth_exceptions import OAuthCredentialsException, UserDisabledException
from handler.auth.constants import ALGORITHM, DEFAULT_OAUTH_TOKEN_EXPIRY, TokenPurpose
from handler.auth.middleware.redis_session_middleware import RedisSessionMiddleware
from handler.email_handler import EmailError, send_email
from handler.redis_handler import redis_client
from logger.formatter import CYAN
from logger.formatter import highlight as hl
from logger.logger import log
from utils.urls import get_public_base_url

oct_key = OctKey.import_key(ROMM_AUTH_SECRET_KEY)

# Anyone who knows a username can ask for its reset link, so its inbox gets at
# most one a minute.
RESET_EMAIL_COOLDOWN_SECONDS = 60


def reset_link_base_url() -> str | None:
    """Where an emailed reset link points; None when links can't be emailed."""
    return get_public_base_url() if EMAIL_ENABLED else None


def _romm_username(provided: str, fallback: str) -> str:
    """A valid, unused RomM username for the name an identity provider chose.

    Args:
        provided (str): The username as the provider sent it
        fallback (str): Stem to use when nothing usable survives sanitizing

    Returns:
        str: A username no other account holds

    Raises:
        HTTPException: If another account already holds that username
    """
    # Deferred: `utils.validation` reaches this module through `models.user`,
    # so importing it at module level closes a cycle.
    from handler.database import db_user_handler
    from utils.validation import sanitize_username

    username = sanitize_username(provided, fallback=fallback)
    if username != provided:
        log.info(
            "OIDC username '%s' is not a valid RomM username, registering as '%s'",
            hl(provided, color=CYAN),
            hl(username, color=CYAN),
        )

    if db_user_handler.get_user_by_username(username) is not None:
        log.error(
            "OIDC username '%s' is already taken by another account",
            hl(username, color=CYAN),
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{username}' is already taken. Please contact an administrator.",
        )

    return username


def _invite_token_spent() -> HTTPException:
    """The one response for a spent or unusable invite, so neither caller
    distinguishes them."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invite token has already been used or is invalid.",
    )


class AuthHandler:
    def __init__(self) -> None:
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.reset_passwd_token_expires_in_minutes = 10

    @staticmethod
    def generate_client_token() -> str:
        return "rmm_" + secrets.token_hex(32)

    @staticmethod
    def hash_client_token(raw: str) -> str:
        return hashlib.sha256(raw.encode()).hexdigest()

    def verify_password(self, plain_password, hashed_password):
        try:
            return self.pwd_context.verify(plain_password, hashed_password)
        except ValueError:
            # OIDC-provisioned accounts hold a placeholder, not a bcrypt hash,
            # and passlib raises on one it cannot identify.
            return False

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

    def generate_password_reset_token(self, user: Any) -> str:
        """A single-use reset token for the user, valid for a few minutes."""
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
        redis_client.setex(
            f"reset-jti:{jti}", self.reset_passwd_token_expires_in_minutes * 60, "valid"
        )
        return token

    def send_password_reset_link(self, user: Any) -> None:
        """Email the user a reset link, or log it for an admin to pass on."""
        # ROMM_BASE_URL alone, so a forged Host header can't point it elsewhere.
        base_url = reset_link_base_url()
        if not (base_url and user.email):
            self._log_password_reset_link(
                user, self.generate_password_reset_token(user)
            )
            return

        if not redis_client.set(
            f"reset-email:{user.id}", "1", ex=RESET_EMAIL_COOLDOWN_SECONDS, nx=True
        ):
            log.info(
                f"A reset link went to {hl(user.username, color=CYAN)} less than a minute ago, not sending another"
            )
            return

        token = self.generate_password_reset_token(user)
        try:
            send_email(
                user.email,
                "Reset your RomM password",
                f"Someone asked to reset the password of your RomM account, "
                f"{user.username}.\n\nChoose a new one within "
                f"{self.reset_passwd_token_expires_in_minutes} minutes here:\n"
                f"{base_url}/reset-password?token={token}\n\n"
                "If it wasn't you, ignore this email and your password stays as it is.",
            )
        except EmailError as exc:
            log.error(
                f"Could not email the reset link to {hl(user.username, color=CYAN)}: {exc}"
            )
            self._log_password_reset_link(user, token)
            return
        log.info(f"Reset password link emailed to {hl(user.username, color=CYAN)}")

    def _log_password_reset_link(self, user: Any, token: str) -> None:
        log.info(
            f"Reset password link requested for {hl(user.username, color=CYAN)}. Reset link: {hl(f'{ROMM_BASE_URL}/reset-password?token={token}')}"
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

    async def apply_user_update(
        self,
        user_id: int,
        data: dict[str, Any],
        revoke_sessions_for: str | None = None,
    ) -> None:
        """
        Write an update to a user, revoking that account's sessions around it.
        Args:
            user_id (int): The user the update applies to.
            data (dict[str, Any]): The fields to write.
            revoke_sessions_for (str | None): Username the sessions are keyed by,
                or None to write without revoking.
        """
        from handler.database import db_user_handler

        if revoke_sessions_for:
            # Ahead of the write: an unreachable Redis then aborts the change
            # rather than committing it with the account's sessions left live.
            await RedisSessionMiddleware.clear_user_sessions(revoke_sessions_for)

        db_user_handler.update_user(user_id, data)

        if revoke_sessions_for:
            # After it, for a login the old password was still good for. The
            # write has committed, so a failure here is logged, not raised.
            try:
                await RedisSessionMiddleware.clear_user_sessions(revoke_sessions_for)
            except RedisError, OSError:
                log.error(
                    "Credentials for '%s' changed, but revoking its sessions "
                    "afterwards failed; a session created during the update may "
                    "still be live",
                    hl(revoke_sessions_for, color=CYAN),
                    exc_info=True,
                )

    async def set_user_new_password(self, user: Any, new_password: str) -> None:
        """
        Set the new password for the user.
        Args:
            user (Any): The user object.
            new_password (str): The new password to set.
        """
        await self.apply_user_update(
            user.id,
            {"hashed_password": self.get_password_hash(new_password)},
            revoke_sessions_for=user.username,
        )

    def generate_invite_link_token(
        self, user: Any, role: str, expiration: int | None = None
    ) -> str:
        """
        Generate an invite link token for the user.
        Args:
            user (Any): The user object.
            role (str): The role of the user.
            expiration (int | None): Token expiration in seconds. Defaults to
                the INVITE_TOKEN_EXPIRY_SECONDS environment variable.
        Returns:
            str: The generated invite link token.
        """
        expires_in = (
            expiration if expiration is not None else INVITE_TOKEN_EXPIRY_SECONDS
        )
        now = datetime.now(timezone.utc)

        jti = str(uuid.uuid4())

        to_encode = {
            "sub": user.username,
            "type": TokenPurpose.INVITE,
            "role": role.upper(),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
            "jti": jti,
        }
        token = jwt.encode(
            {"alg": ALGORITHM},
            to_encode,
            oct_key,
        )
        # The link is already in the response; the token registers an account on
        # its own, so the log gets only its id.
        log.info(
            f"Invite link created by {hl(user.username, color=CYAN)} (jti: {hl(jti)})"
        )
        redis_client.setex(f"invite-jti:{jti}", expires_in, "valid")
        return token

    def assert_invite_link_token_valid(self, token: str) -> None:
        """Raise unless the invite link token is valid, leaving it unspent.

        Args:
            token (str): The token to check.
        """
        jti, _ = self._decode_invite_link_token(token)
        if redis_client.get(f"invite-jti:{jti}") != b"valid":
            raise _invite_token_spent()

    def consume_invite_link_token(self, token: str) -> str:
        """
        Verify and consume the invite link token, which invalidates the token to prevent reuse.

        Args:
            token (str): The token to verify.

        Returns:
            str: The role associated with the token.
        """
        jti, role = self._decode_invite_link_token(token)

        # Read and invalidate in one operation, so two registrations racing on
        # one invite cannot both see it as valid and both create an account.
        if redis_client.getdel(f"invite-jti:{jti}") != b"valid":
            raise _invite_token_spent()

        return role

    def _decode_invite_link_token(self, token: str) -> tuple[str, str]:
        """Decode an invite link token and return its `(jti, role)`."""
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
        if not jti:
            raise _invite_token_spent()

        return jti, role


class OAuthHandler:
    def __init__(self) -> None:
        pass

    def _create_oauth_token(
        self, data: dict, expires_delta: timedelta = DEFAULT_OAUTH_TOKEN_EXPIRY
    ) -> str:
        to_encode = data.copy()
        expire = int((datetime.now(timezone.utc) + expires_delta).timestamp())
        to_encode["exp"] = expire

        return jwt.encode(
            {"alg": ALGORITHM},
            to_encode,
            oct_key,
        )

    def create_access_token(
        self, data: dict, expires_delta: timedelta = DEFAULT_OAUTH_TOKEN_EXPIRY
    ) -> str:
        to_encode = data.copy()
        to_encode["type"] = "access"
        return self._create_oauth_token(to_encode, expires_delta)

    def create_refresh_token(self, data: dict, expires_delta: timedelta) -> str:
        if expires_delta <= timedelta(0):
            raise ValueError("expires_delta must be positive for refresh tokens")

        to_encode = data.copy()
        jti = str(uuid.uuid4())
        to_encode.update(
            {
                "jti": jti,
                "type": "refresh",
            }
        )

        token = self._create_oauth_token(to_encode, expires_delta)

        redis_client.setex(
            f"refresh-jti:{jti}",
            int(expires_delta.total_seconds()),
            "valid",
        )

        return token

    async def consume_refresh_token(self, token: str):
        from handler.database import db_user_handler

        try:
            payload = jwt.decode(token, oct_key, algorithms=[ALGORITHM])
        except (BadSignatureError, DecodeError, ValueError) as exc:
            raise OAuthCredentialsException from exc

        now = datetime.now(timezone.utc).timestamp()
        if now > payload.claims.get("exp", 0):
            raise OAuthCredentialsException

        if payload.claims.get("iss") != "romm:oauth":
            raise OAuthCredentialsException

        if payload.claims.get("type") != "refresh":
            raise OAuthCredentialsException

        jti = payload.claims.get("jti")
        if not jti or redis_client.getdel(f"refresh-jti:{jti}") != b"valid":
            raise OAuthCredentialsException

        username = payload.claims.get("sub")
        if not username:
            raise OAuthCredentialsException

        user = db_user_handler.get_user_by_username(username)
        if user is None:
            raise OAuthCredentialsException

        if not user.enabled:
            raise UserDisabledException

        return user, payload.claims

    async def get_current_active_user_from_bearer_token(self, token: str):
        from handler.database import db_user_handler

        try:
            payload = jwt.decode(token, oct_key, algorithms=[ALGORITHM])
        except (BadSignatureError, DecodeError, ValueError) as exc:
            raise OAuthCredentialsException from exc

        now = datetime.now(timezone.utc).timestamp()
        if now > payload.claims.get("exp", 0):
            raise OAuthCredentialsException

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
        from handler.audit_handler import SYSTEM_ACTOR, AuditActor, AuditTarget, record
        from handler.database import db_user_handler
        from models.audit_event import AuditAction
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

        preferred_username = userinfo.get(OIDC_USERNAME_ATTRIBUTE)
        if preferred_username is None:
            log.error(f"'{OIDC_USERNAME_ATTRIBUTE}' attribute is missing from token.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{OIDC_USERNAME_ATTRIBUTE}' attribute is missing from token.",
            )

        # Admin claim grants admin; the legacy editor/viewer claims both map to
        # the single `user` kind now (env var names kept to avoid a breaking
        # ops rename). No matching claim -> no access.
        role = Role.USER
        claims_provided = OIDC_CLAIM_ROLES and OIDC_CLAIM_ROLES in userinfo
        if claims_provided:
            roles = userinfo[OIDC_CLAIM_ROLES] or []
            if OIDC_ROLE_ADMIN and OIDC_ROLE_ADMIN in roles:
                role = Role.ADMIN
            elif (OIDC_ROLE_EDITOR and OIDC_ROLE_EDITOR in roles) or (
                OIDC_ROLE_VIEWER
                and (OIDC_ROLE_VIEWER in roles or OIDC_ROLE_VIEWER == "*")
            ):
                role = Role.USER
            else:
                log.error("User has not been granted any roles for this application.")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User has not been granted any roles for this application.",
                )

        user = db_user_handler.get_user_by_email(email)
        if user is None:
            if not OIDC_ALLOW_REGISTRATION:
                log.error(
                    "User with email '%s' not found and OIDC registration is disabled",
                    hl(email, color=CYAN),
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User registration is disabled. Please contact an administrator to create an account.",
                )
            log.info(
                "User with email '%s' not found, creating new user",
                hl(email, color=CYAN),
            )
            username = _romm_username(preferred_username, fallback=email.split("@")[0])
            new_user = User(
                username=username,
                hashed_password=str(uuid.uuid4()),
                email=email,
                enabled=True,
                role=role,
            )
            user = db_user_handler.add_user(new_user)
            record(
                AuditAction.USER_REGISTER,
                AuditActor.for_user(user),
                AuditTarget.of_user(user),
                {"role": user.role, "via": "oidc"},
            )
        elif claims_provided and user.role != role:
            previous_role = user.role
            user = db_user_handler.update_user(user.id, {"role": role})
            record(
                AuditAction.USER_EDIT,
                SYSTEM_ACTOR,
                AuditTarget.of_user(user),
                {
                    "changed": ["role"],
                    "role": {"from": previous_role, "to": role},
                    "via": "oidc",
                },
            )

        if not user.enabled:
            raise UserDisabledException

        log.info("User successfully authenticated: %s", hl(email, color=CYAN))
        return user, userinfo
