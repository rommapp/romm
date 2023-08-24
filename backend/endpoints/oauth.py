from typing import Annotated, Final
from datetime import timedelta
from fastapi import Depends, APIRouter, HTTPException, status


from utils.auth import authenticate_user
from utils.oauth import (
    OAuth2RequestForm,
    create_oauth_token,
    get_current_active_user_from_bearer_token,
)


ACCESS_TOKEN_EXPIRE_MINUTES: Final = 30
REFRESH_TOKEN_EXPIRE_DAYS: Final = 7

router = APIRouter()


@router.post("/token")
async def token(form_data: Annotated[OAuth2RequestForm, Depends()]):
    """OAuth2 token endpoint"""

    # Suppport refreshing access tokens
    if form_data.grant_type == "refresh_token":
        token = form_data.refresh_token
        if not token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Missing refresh token"
            )

        user, payload = await get_current_active_user_from_bearer_token(token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        access_token = create_oauth_token(
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

        user = authenticate_user(form_data.username, form_data.password)
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

    access_token = create_oauth_token(
        data={
            "sub": user.username,
            "scopes": " ".join(form_data.scopes),
            "type": "access",
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    refresh_token = create_oauth_token(
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
