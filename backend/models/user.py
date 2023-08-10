from sqlalchemy import Column, String, Boolean, Integer
from starlette.authentication import SimpleUser
from .base import BaseModel

class User(SimpleUser, BaseModel):
    __tablename__ = "users"
    id = Column(Integer(), primary_key=True, autoincrement=True)
    username: str = Column(String(length=255), unique=True, index=True)
    hashed_password: str = Column(String(length=255))
    disabled: bool = Column(Boolean(), default=False)

