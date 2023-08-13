from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import HTTPException, status, Security
from fastapi.param_functions import Form
from fastapi.security.oauth2 import OAuth2PasswordBearer

from config import ROMM_AUTH_SECRET_KEY

ALGORITHM = "HS256"

DEFAULT_SCOPES_MAP = {
    "me.read": "View your profile",
    "me.write": "Modify your profile",
    "roms.read": "View ROMs",
    "platforms.read": "View platforms",
}

WRITE_SCOPES_MAP = {
    "roms.write": "Modify ROMs",
    "platforms.write": "Modify platforms",
}

FULL_SCOPES_MAP = {
    "users.read": "View users",
    "users.write": "Modify users",
}

DEFAULT_SCOPES = list(DEFAULT_SCOPES_MAP.keys())
WRITE_SCOPES = DEFAULT_SCOPES + list(WRITE_SCOPES_MAP.keys())
FULL_SCOPES = WRITE_SCOPES + list(FULL_SCOPES_MAP.keys())

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def create_oauth_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, ROMM_AUTH_SECRET_KEY, algorithm=ALGORITHM)


async def get_current_active_user_from_token(token: str):
    from handler import dbh

    try:
        payload = jwt.decode(token, ROMM_AUTH_SECRET_KEY, algorithms=[ALGORITHM])
    except (JWTError):
        raise credentials_exception

    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    user = dbh.get_user(username)
    if user is None:
        raise credentials_exception

    if user.disabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user"
        )

    return user, payload


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


oauth2_password_bearer = OAuth2PasswordBearer(
    tokenUrl="/token",
    scopes={
        **DEFAULT_SCOPES_MAP,
        **WRITE_SCOPES_MAP,
        **FULL_SCOPES_MAP,
    },
)


def protected_route(method, path: str, scopes: list[str] = []):
    return method(
        path,
        dependencies=[
            Security(
                dependency=oauth2_password_bearer,
                scopes=scopes,
            ),
        ],
    )
