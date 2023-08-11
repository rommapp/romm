from datetime import datetime, timedelta
from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
)
from starlette.requests import HTTPConnection

from handler import dbh
from config import SECRET_KEY
from utils.cache import cache

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def authenticate_user(username: str, password: str):
    user = dbh.get_user(username)
    if not user:
        return False

    if not verify_password(password, user.hashed_password):
        return False

    return user


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


class BasicAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn: HTTPConnection):
        # Check if session key already stored in cache
        session_id = conn.session.get("session_id")
        if session_id:
            username = cache.get(f"romm:{session_id}")
            if username:
                # Key exists therefore user is authenticated
                user = dbh.get_user(username)
                if user is None:
                    raise credentials_exception

                if user.disabled:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
                    )

                return (AuthCredentials(user.oauth_scopes), user)

        # Check if Authorization header exists
        if "Authorization" not in conn.headers:
            return

        auth = conn.headers["Authorization"]
        scheme, token = auth.split()
        if scheme.lower() != "bearer":
            return

        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
                status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
            )

        return (AuthCredentials(user.oauth_scopes), user)
