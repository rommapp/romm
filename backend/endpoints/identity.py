from typing import Annotated
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
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


class TokenSchema(BaseModel):
    access_token: str
    token_type: str


class UserSchema(BaseModel):
    username: str
    disabled: bool

    class Config(BaseConfig):
        orm_mode = True


@router.post("/token", response_model=TokenSchema)
def login_with_password(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
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

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me/", response_model=UserSchema)
def current_user(current_user: Annotated[User, Depends(get_current_active_user)]):
    return current_user


@router.post("/users/", response_model=UserSchema)
def create_user(username: str, password: str):
    user = User(
        username=username, hashed_password=get_password_hash(password), disabled=False
    )
    dbh.add_user(user)
    return user
