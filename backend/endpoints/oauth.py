from datetime import timedelta
from typing import Annotated, Final

from endpoints.forms.identity import OAuth2RequestForm
from endpoints.responses.oauth import TokenResponse
from fastapi import APIRouter, Depends, HTTPException, status
from handler import authh, oauthh

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

        user, payload = await oauthh.get_current_active_user_from_bearer_token(token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        access_token = oauthh.create_oauth_token(
            data={
                "sub": user.username,
                "scopes": payload.get("scopes"),
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

        user = authh.authenticate_user(form_data.username, form_data.password)
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

    access_token = oauthh.create_oauth_token(
        data={
            "sub": user.username,
            "scopes": " ".join(form_data.scopes),
            "type": "access",
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    refresh_token = oauthh.create_oauth_token(
        data={
            "sub": user.username,
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
