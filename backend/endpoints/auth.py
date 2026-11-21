import asyncio
from datetime import datetime, timedelta, timezone
from typing import Annotated, Final, Literal, Optional, cast
from urllib.parse import urlencode

from authlib.common.errors import AuthlibBaseError
from fastapi import BackgroundTasks, Body, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security.http import HTTPBasic, HTTPBasicCredentials
from httpx2 import HTTPError
from joserfc.errors import JoseError

from config import (
    OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS,
    OAUTH_REFRESH_TOKEN_EXPIRE_SECONDS,
    OIDC_ENABLED,
    OIDC_END_SESSION_ENDPOINT,
    OIDC_REDIRECT_URI,
    OIDC_RP_INITIATED_LOGOUT,
)
from decorators.auth import oauth
from endpoints.forms.identity import OAuth2RequestForm
from endpoints.responses.oauth import OIDCLogoutResponse, TokenResponse
from exceptions.auth_exceptions import (
    AuthCredentialsException,
    OIDCDisabledException,
    OIDCNotConfiguredException,
    UserDisabledException,
)
from handler.audit_handler import (
    AuditActor,
    AuditTarget,
    claim_once,
    client_ip,
    record,
    release_claim,
    within_budget,
)
from handler.auth.base_handler import auth_handler, oauth_handler, oidc_handler
from handler.database import db_user_handler
from logger.formatter import CYAN
from logger.formatter import highlight as hl
from logger.logger import log
from models.audit_event import AuditAction
from models.user import User
from utils.auth import create_or_find_web_device
from utils.router import APIRouter
from utils.validation import ValidationError, validate_password

router = APIRouter(
    tags=["auth"],
)


# Failed sign-ins from one address for one username within this window are one attempt.
LOGIN_FAILURE_WINDOW_SECONDS: Final = 60
# At most this many failed sign-ins are recorded per address each window, so a
# client cycling usernames can't flood the log.
LOGIN_FAILURES_PER_ADDRESS: Final = 20
LOGIN_FAILURE_ADDRESS_WINDOW_SECONDS: Final = 10 * 60
# Repeated reset requests for one user from one address are one request.
PASSWORD_RESET_REQUEST_WINDOW_SECONDS: Final = 10 * 60

LoginMethod = Literal["password", "token", "oidc"]


def _record_login(
    request: Request, user: User, method: LoginMethod, device_id: str | None = None
) -> None:
    record(
        AuditAction.AUTH_LOGIN,
        AuditActor.for_user(user, ip_address=client_ip(request), device_id=device_id),
        data={"method": method},
    )


def _record_login_failure(
    request: Request,
    username: str | None,
    method: LoginMethod,
    reason: Literal["credentials", "disabled"],
) -> None:
    ip_address = client_ip(request)
    key = f"login_failed:{ip_address}:{username}"
    if not claim_once(key, LOGIN_FAILURE_WINDOW_SECONDS) or not within_budget(
        f"login_failed:{ip_address}",
        LOGIN_FAILURES_PER_ADDRESS,
        LOGIN_FAILURE_ADDRESS_WINDOW_SECONDS,
    ):
        return
    user = db_user_handler.get_user_by_username(username) if username else None
    # A name that matches no account may be a password typed in the wrong box,
    # so only an account's own name is kept.
    if not record(
        AuditAction.AUTH_LOGIN_FAILED,
        (
            AuditActor.for_user(user, ip_address=ip_address)
            if user
            else AuditActor.anonymous(ip_address)
        ),
        data={
            "username": user.username if user else None,
            "method": method,
            "reason": reason,
        },
    ):
        release_claim(key)


def _record_password_reset_request(ip_address: str | None, user: User) -> None:
    key = f"password_reset:{ip_address}:{user.id}"
    if claim_once(key, PASSWORD_RESET_REQUEST_WINDOW_SECONDS) and not record(
        AuditAction.AUTH_PASSWORD_RESET_REQUEST,
        AuditActor.anonymous(ip_address),
        AuditTarget.of_user(user),
    ):
        release_claim(key)


# Session authentication endpoints
@router.post(
    "/login",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "The username and password are not valid, or the user is disabled."
        }
    },
)
def login(
    request: Request,
    credentials: HTTPBasicCredentials = Depends(HTTPBasic()),  # noqa
) -> None:
    """Sign in with HTTP Basic credentials and start a session."""

    user = auth_handler.authenticate_user(credentials.username, credentials.password)
    if not user:
        _record_login_failure(request, credentials.username, "password", "credentials")
        raise AuthCredentialsException

    if not user.enabled:
        _record_login_failure(request, credentials.username, "password", "disabled")
        raise UserDisabledException

    request.session["iss"] = "romm:auth"
    request.session["sub"] = user.username

    # Auto-create or find the web browser device
    device = create_or_find_web_device(request, user)
    request.session["device_id"] = device.id

    # Update last login and active times
    now = datetime.now(timezone.utc)
    db_user_handler.update_user(user.id, {"last_login": now, "last_active": now})
    _record_login(request, user, "password", device.id)


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(request: Request) -> Optional[OIDCLogoutResponse]:
    """End the session. After an OIDC sign-in with RP-Initiated Logout enabled, the response holds the provider's end-session URL."""

    id_token = request.session.get("oidc_id_token")
    request.session.clear()

    if OIDC_RP_INITIATED_LOGOUT and id_token:
        end_session_endpoint = OIDC_END_SESSION_ENDPOINT
        if not end_session_endpoint and oauth.openid:
            try:
                metadata = await oauth.openid.load_server_metadata()
                end_session_endpoint = metadata.get("end_session_endpoint", "")
            except Exception:
                log.warning(
                    "Failed to load OIDC server metadata for RP-Initiated Logout"
                )

        if end_session_endpoint:
            params = urlencode({"id_token_hint": id_token})
            return {"oidc_logout_url": f"{end_session_endpoint}?{params}"}

    return None


@router.post(
    "/token",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "A required field is missing, or the grant type is not supported."
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": (
                "The username and password are not valid, or the refresh token is"
                " not valid or belongs to a disabled user."
            )
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "The account is disabled, or the requested scopes are not granted to it."
        },
    },
)
async def token(
    request: Request, form_data: Annotated[OAuth2RequestForm, Depends()]
) -> TokenResponse:
    """Issue an access token and a refresh token, from a username and password or from a refresh token."""

    user: User | None
    # Read before any credential check, so a revocation that lands during the
    # check still covers the tokens issued below.
    issued_at = datetime.now(timezone.utc)
    # Support refreshing access tokens
    if form_data.grant_type == "refresh_token":
        token = form_data.refresh_token
        if not token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Missing refresh token"
            )

        user, claims = await oauth_handler.consume_refresh_token(token)
        if not user or not claims:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        if not user.enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled"
            )

        access_token = oauth_handler.create_access_token(
            data={
                "sub": user.username,
                "iss": "romm:oauth",
                "scopes": claims.get("scopes"),
            },
            expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
            issued_at=issued_at,
        )

        refresh_token = oauth_handler.create_refresh_token(
            data={
                "sub": user.username,
                "iss": "romm:oauth",
                "scopes": claims.get("scopes"),
            },
            expires_delta=timedelta(seconds=OAUTH_REFRESH_TOKEN_EXPIRE_SECONDS),
            issued_at=issued_at,
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",  # trunk-ignore(bandit/B105)
            "expires": OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS,
            "refresh_expires": OAUTH_REFRESH_TOKEN_EXPIRE_SECONDS,
        }

    # Authentication via username/password
    elif form_data.grant_type == "password":
        if not form_data.username or not form_data.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing username or password",
            )

        user = await asyncio.to_thread(
            auth_handler.authenticate_user, form_data.username, form_data.password
        )
        if not user:
            _record_login_failure(request, form_data.username, "token", "credentials")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )

        if not user.enabled:
            _record_login_failure(request, form_data.username, "token", "disabled")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled"
            )

    # TODO: Authentication via client_id/client_secret
    elif form_data.grant_type == "client_credentials":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client credentials are not yet supported",
        )

    else:
        # All other grant types are unsupported
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or unsupported grant type",
        )

    # Check if user has access to requested scopes
    if not set(form_data.scopes).issubset(user.oauth_scopes):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient scope",
        )

    access_token = oauth_handler.create_access_token(
        data={
            "sub": user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(form_data.scopes),
        },
        expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
        issued_at=issued_at,
    )

    refresh_token = oauth_handler.create_refresh_token(
        data={
            "sub": user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(form_data.scopes),
        },
        expires_delta=timedelta(seconds=OAUTH_REFRESH_TOKEN_EXPIRE_SECONDS),
        issued_at=issued_at,
    )
    _record_login(request, user, "token")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",  # trunk-ignore(bandit/B105)
        "expires": OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS,
        "refresh_expires": OAUTH_REFRESH_TOKEN_EXPIRE_SECONDS,
    }


# OIDC login and callback endpoints
@router.get(
    "/login/openid",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "OIDC is disabled or not configured."
        }
    },
)
async def login_via_openid(request: Request) -> RedirectResponse:
    """Redirect to the OIDC provider to sign in, or to the login page if the provider cannot be reached."""

    if not OIDC_ENABLED:
        raise OIDCDisabledException

    if not oauth.openid:
        raise OIDCNotConfiguredException

    # Authlib fetches the provider's discovery document here, so a wrong
    # OIDC_SERVER_APPLICATION_URL surfaces as an HTTP error
    try:
        return cast(
            RedirectResponse,
            await oauth.openid.authorize_redirect(request, OIDC_REDIRECT_URI),
        )
    except HTTPError as exc:
        log.error(
            f"OIDC provider discovery failed, check OIDC_SERVER_APPLICATION_URL: {exc!r}"
        )
        # Without the bypass, OIDC autologin would send the failure straight
        # back here and loop
        return RedirectResponse(url="/login?bypass_autologin=true")


@router.get(
    "/oauth/openid",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "The provider's token lacks the user info, email or username, or the email is not verified."
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "No user matches the identity, or the user is disabled."
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "The user has no role for RomM, the account is linked to another identity, or registration is disabled."
        },
        status.HTTP_409_CONFLICT: {
            "description": (
                "The identity provider's username for a new user is already taken"
                " by another account."
            )
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "OIDC is disabled or not configured."
        },
    },
)
async def auth_openid(request: Request) -> RedirectResponse:
    """Complete an OIDC sign-in, then redirect to the home page, or to the login page if the provider rejects it."""

    if not OIDC_ENABLED:
        raise OIDCDisabledException

    if not oauth.openid:
        raise OIDCNotConfiguredException

    # Authlib verifies the ID token with joserfc, whose errors are not Authlib's.
    try:
        token = await oauth.openid.authorize_access_token(request)
    except (AuthlibBaseError, JoseError) as exc:
        # repr() because error and description can come from the query string
        log.warning(f"OIDC callback rejected: {exc.error!r}: {exc.description!r}")
        if request.user.is_authenticated and not request.user.is_kiosk_guest:
            return RedirectResponse(url="/")
        # Without the bypass, OIDC autologin would send a persistent failure
        # straight back to the provider and loop
        return RedirectResponse(url="/login?bypass_autologin=true")
    potential_user, _userinfo = (
        await oidc_handler.get_current_active_user_from_openid_token(token)
    )

    if not potential_user:
        _record_login_failure(request, None, "oidc", "credentials")
        raise AuthCredentialsException

    if not potential_user.enabled:
        _record_login_failure(request, potential_user.username, "oidc", "disabled")
        raise UserDisabledException

    request.session["iss"] = "romm:auth"
    request.session["sub"] = potential_user.username
    if OIDC_RP_INITIATED_LOGOUT:
        request.session["oidc_id_token"] = token.get("id_token", "")

    # Auto-create or find the web browser device
    device = create_or_find_web_device(request, potential_user)
    request.session["device_id"] = device.id

    # Update last login and active times
    now = datetime.now(timezone.utc)
    db_user_handler.update_user(
        potential_user.id, {"last_login": now, "last_active": now}
    )
    _record_login(request, potential_user, "oidc", device.id)

    return RedirectResponse(url="/")


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def request_password_reset(
    request: Request,
    background_tasks: BackgroundTasks,
    username: str = Body(..., embed=True),
) -> None:
    """Email a password reset link to the user. The response is the same whether or not the username exists."""
    user = db_user_handler.get_user_by_username(username)

    if user:
        # After the response, so its timing can't tell whether the user exists.
        # The record goes first: a link that fails to send stops the tasks after it.
        background_tasks.add_task(
            _record_password_reset_request, client_ip(request), user
        )
        background_tasks.add_task(auth_handler.send_password_reset_link, user)
    else:
        log.warning(
            f"Reset password link requested for a user {hl(username, color=CYAN)}, but that username does not exist."
        )


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": (
                "The new password is not valid, or the token is not valid, already"
                " used or expired."
            )
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "The user the token was issued for no longer exists."
        },
    },
)
async def reset_password(
    request: Request,
    token: str = Body(..., embed=True),
    new_password: str = Body(..., embed=True),
) -> None:
    """Set a new password with the token from a password reset link. The token works once."""
    # Ahead of the token check, which spends the link: a rejected password
    # leaves it usable for another try.
    try:
        validate_password(new_password)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc

    user = auth_handler.verify_password_reset_token(token)

    await auth_handler.set_user_new_password(user, new_password)
    record(
        AuditAction.AUTH_PASSWORD_RESET,
        AuditActor.for_user(user, ip_address=client_ip(request)),
        AuditTarget.of_user(user),
    )

    log.info(
        f"Password was successfully reset for user {hl(user.username, color=CYAN)}."
    )
