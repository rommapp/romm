from datetime import datetime, timedelta
from typing import Annotated, Final

from endpoints.forms.identity import OAuth2RequestForm
from endpoints.responses import MessageResponse
from endpoints.responses.oauth import TokenResponse
from exceptions.auth_exceptions import AuthCredentialsException, DisabledException
from fastapi import Depends, HTTPException, Request, status
from fastapi.security.http import HTTPBasic
from handler.auth import auth_handler, oauth_handler
from handler.database import db_user_handler
from utils.router import APIRouter

ACCESS_TOKEN_EXPIRE_MINUTES: Final = 30
REFRESH_TOKEN_EXPIRE_DAYS: Final = 7

router = APIRouter()


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
        if claims.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
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


@router.post("/login")
def login(
    request: Request, credentials=Depends(HTTPBasic())  # noqa
) -> MessageResponse:
    """Session login endpoint

    Args:
        request (Request): Fastapi Request object
        credentials: Defaults to Depends(HTTPBasic()).

    Raises:
        CredentialsException: Invalid credentials
        DisabledException: Auth is disabled

    Returns:
        MessageResponse: Standard message response
    """

    user = auth_handler.authenticate_user(credentials.username, credentials.password)
    if not user:
        raise AuthCredentialsException

    if not user.enabled:
        raise DisabledException

    request.session.update({"iss": "romm:auth", "sub": user.username})

    # Update last login and active times
    db_user_handler.update_user(
        user.id, {"last_login": datetime.now(), "last_active": datetime.now()}
    )

    return {"msg": "Successfully logged in"}


@router.post("/logout")
def logout(request: Request) -> MessageResponse:
    """Session logout endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        MessageResponse: Standard message response
    """

    request.session.clear()

    return {"msg": "Successfully logged out"}
