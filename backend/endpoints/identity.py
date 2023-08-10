from typing import Annotated
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, BaseConfig

from handler import dbh
from models.user import User
from utils.auth import (
    authenticate_user,
    create_access_token,
    get_current_active_user,
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
def login_with_password(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], response: Response
):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    response.set_cookie(
        "access_token", access_token, httponly=True, secure=True, samesite="strict"
    )

    return user


@router.get(
    "/users/",
    dependencies=[Depends(get_current_active_user)],
)
def users() -> list[UserSchema]:
    return dbh.get_users()


@router.get("/users/me/")
def current_user(
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> UserSchema:
    return current_user


@router.post(
    "/users/",
    dependencies=[Depends(get_current_active_user)],
)
def create_user(username: str, password: str) -> UserSchema:
    user = User(
        username=username, hashed_password=get_password_hash(password), disabled=False
    )
    dbh.add_user(user)
    return user
