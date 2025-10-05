from datetime import datetime, timedelta, timezone
from typing import Annotated, Final

from fastapi import Body, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security.http import HTTPBasic

from config import OIDC_ENABLED, OIDC_REDIRECT_URI
from decorators.auth import oauth
from endpoints.forms.identity import OAuth2RequestForm
from endpoints.responses.oauth import TokenResponse
from exceptions.auth_exceptions import (
    AuthCredentialsException,
    OIDCDisabledException,
    OIDCNotConfiguredException,
    UserDisabledException,
)
from handler.auth import auth_handler, oauth_handler, oidc_handler
from handler.database import db_user_handler
from logger.formatter import CYAN
from logger.formatter import highlight as hl
from logger.logger import log
from utils.router import APIRouter

ACCESS_TOKEN_EXPIRE_MINUTES: Final = 30
REFRESH_TOKEN_EXPIRE_DAYS: Final = 7

router = APIRouter(
    tags=["auth"],
)


# Session authentication endpoints
@router.post("/login")
def login(
    request: Request,
    credentials=Depends(HTTPBasic()),  # noqa
) -> None:
    """Session login endpoint

    Args:
        request (Request): Fastapi Request object
        credentials: Defaults to Depends(HTTPBasic()).

    Raises:
        CredentialsException: Invalid credentials
        UserDisabledException: Auth is disabled
    """

    user = auth_handler.authenticate_user(credentials.username, credentials.password)
    if not user:
        raise AuthCredentialsException

    if not user.enabled:
        raise UserDisabledException

    request.session.update({"iss": "romm:auth", "sub": user.username})

    # Update last login and active times
    now = datetime.now(timezone.utc)
    db_user_handler.update_user(user.id, {"last_login": now, "last_active": now})


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(request: Request) -> None:
    """Session logout endpoint

    Args:
        request (Request): Fastapi Request object
    """

    request.session.clear()


@router.post("/token")
async def token(form_data: Annotated[OAuth2RequestForm, Depends()]) -> TokenResponse:
    """OAuth2 token endpoint

    Args:
        form_data (Annotated[OAuth2RequestForm, Depends): Form Data with OAuth2 info

    Raises:
        HTTPException: Missing refresh token
        HTTPException: Invalid refresh token
        HTTPException: Missing username or password
        HTTPException: Invalid username or password
        HTTPException: Client credentials are not yet supported
        HTTPException: Invalid or unsupported grant type
        HTTPException: Insufficient scope

    Returns:
        TokenResponse: TypedDict with the new generated token info
    """

    # Suppport refreshing access tokens
    if form_data.grant_type == "refresh_token":
        token = form_data.refresh_token
        if not token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Missing refresh token"
            )

        user, claims = await oauth_handler.get_current_active_user_from_bearer_token(
            token
        )
        if not user or not claims:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        if claims.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        if not user.enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled"
            )

        access_token = oauth_handler.create_oauth_token(
            data={
                "sub": user.username,
                "iss": "romm:oauth",
                "scopes": claims.get("scopes"),
                "type": "access",
            },
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    # Authentication via username/password
    elif form_data.grant_type == "password":
        if not form_data.username or not form_data.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing username or password",
            )

        user = auth_handler.authenticate_user(form_data.username, form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )

        if not user.enabled:
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

    access_token = oauth_handler.create_oauth_token(
        data={
            "sub": user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(form_data.scopes),
            "type": "access",
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    refresh_token = oauth_handler.create_oauth_token(
        data={
            "sub": user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(form_data.scopes),
            "type": "refresh",
        },
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


# OIDC login and callback endpoints
@router.get("/login/openid")
async def login_via_openid(request: Request):
    """OIDC login endpoint

    Args:
        request (Request): Fastapi Request object

    Raises:
        OIDCDisabledException: OAuth is disabled
        OIDCNotConfiguredException: OAuth not configured

    Returns:
        RedirectResponse: Redirect to OIDC provider
    """

    if not OIDC_ENABLED:
        raise OIDCDisabledException

    if not oauth.openid:
        raise OIDCNotConfiguredException

    return await oauth.openid.authorize_redirect(request, OIDC_REDIRECT_URI)


@router.get("/oauth/openid")
async def auth_openid(request: Request):
    """OIDC callback endpoint

    Args:
        request (Request): Fastapi Request object

    Raises:
        OIDCDisabledException: OAuth is disabled
        OIDCNotConfiguredException: OAuth not configured
        AuthCredentialsException: Invalid credentials
        UserDisabledException: Auth is disabled

    Returns:
        RedirectResponse: Redirect to home page
    """

    if not OIDC_ENABLED:
        raise OIDCDisabledException

    if not oauth.openid:
        raise OIDCNotConfiguredException

    token = await oauth.openid.authorize_access_token(request)
    potential_user, _userinfo = (
        await oidc_handler.get_current_active_user_from_openid_token(token)
    )

    if not potential_user:
        raise AuthCredentialsException

    if not potential_user.enabled:
        raise UserDisabledException

    request.session.update({"iss": "romm:auth", "sub": potential_user.username})

    # Update last login and active times
    now = datetime.now(timezone.utc)
    db_user_handler.update_user(
        potential_user.id, {"last_login": now, "last_active": now}
    )

    return RedirectResponse(url="/")


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def request_password_reset(username: str = Body(..., embed=True)) -> None:
    """Request a password reset link for the user.

    Args:
        username (str): Username of the user requesting the reset
    Returns:
        None: Returns 200 OK status
    """
    user = db_user_handler.get_user_by_username(username)

    if user:
        auth_handler.generate_password_reset_token(user)
    else:
        log.warning(
            f"Reset password link requested for a user {hl(username, color=CYAN)}, but that username does not exist."
        )


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(
    token: str = Body(..., embed=True),
    new_password: str = Body(..., embed=True),
) -> None:
    """Reset password using the token.

    Args:
        token (str): Reset token from the URL
        new_password (str): New user password

    Returns:
        None: Returns 200 OK status
    """
    user = auth_handler.verify_password_reset_token(token)

    auth_handler.set_user_new_password(user, new_password)

    log.info(
        f"Password was successfully reset for user {hl(user.username, color=CYAN)}."
    )
