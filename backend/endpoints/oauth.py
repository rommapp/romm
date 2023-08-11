from typing import Annotated, Optional
from datetime import timedelta
from fastapi import Depends, APIRouter, HTTPException, status
from fastapi.param_functions import Form


from utils.auth import (
    authenticate_user,
    create_oauth_token,
    get_current_active_user_from_token,
)


ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

router = APIRouter()


class OAuth2RequestForm:
    def __init__(
        self,
        grant_type: str = Form(default="password"),
        scope: str = Form(default=""),
        username: Optional[str] = Form(default=None),
        password: Optional[str] = Form(default=None),
        client_id: Optional[str] = Form(default=None),
        client_secret: Optional[str] = Form(default=None),
        refresh_token: Optional[str] = Form(default=None),
    ):
        self.grant_type = grant_type
        self.scopes = scope.split()
        self.username = username
        self.password = password
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token


def credentials_exception(details: str):
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=details,
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/oauth/token")
async def oauth(form_data: Annotated[OAuth2RequestForm, Depends()]):
    # Suppport refreshing access tokens
    if form_data.grant_type == "refresh_token":
        token = form_data.refresh_token
        if not token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing refresh token"
            )
        
        user, payload = await get_current_active_user_from_token(token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        access_token = create_oauth_token(
            data={"sub": user.username, "type": "access"},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    
    # Authentication via username/password
    elif form_data.grant_type == "password":
        user = authenticate_user(form_data.username, form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )
    
    # TODO: Authentication via client_id/client_secret
    # Should also support specifying scopes
    elif form_data.grant_type == "client_credentials":
        pass

    else:
        # All other grant types are unsupported
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid grant type",
        )

    access_token = create_oauth_token(
        data={"sub": user.username, "type": "access"},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    refresh_token = create_oauth_token(
        data={"sub": user.username, "type": "refresh"},
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }
