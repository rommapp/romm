from typing import Annotated
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, BaseConfig
from starlette.authentication import requires

from handler import dbh
from models.user import User
from utils.auth import (
    authenticate_user,
    create_access_token,
    get_password_hash,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

router = APIRouter()


class UserSchema(BaseModel):
    username: str
    disabled: bool

    class Config(BaseConfig):
        orm_mode = True


@router.post("/token", response_model=UserSchema)
def generate_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], request: Request
):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Authorization"},
        )

    create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return user


@router.post("/login")
def login(request: Request):
    if request.user.is_authenticated:
        return {"message": "Successfully logged in"}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Authorization"},
    )


@router.get("/users")
@requires(["authenticated", "admin"])
def users(request: Request) -> list[UserSchema]:
    return dbh.get_users()


@router.get("/users/me")
@requires("authenticated")
def current_user(request: Request) -> UserSchema:
    return request.user


@router.post("/users/")
@requires(["authenticated", "admin"])
def create_user(request: Request, username: str, password: str) -> UserSchema:
    user = User(
        username=username, hashed_password=get_password_hash(password), disabled=False
    )
    dbh.add_user(user)
    return user
