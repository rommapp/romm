import enum

from handler.auth_handler import DEFAULT_SCOPES, FULL_SCOPES, WRITE_SCOPES
from models.base import BaseModel
from sqlalchemy import Boolean, Column, Enum, Integer, String
from starlette.authentication import SimpleUser


class Role(enum.Enum):
    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"


class User(BaseModel, SimpleUser):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer(), primary_key=True, autoincrement=True)

    username: str = Column(String(length=255), unique=True, index=True)
    hashed_password: str = Column(String(length=255))

    enabled: bool = Column(Boolean(), default=True)

    role: Role = Column(Enum(Role), default=Role.VIEWER)

    avatar_path: str = Column(String(length=255), default="")

    @property
    def oauth_scopes(self):
        if self.role == Role.ADMIN:
            return FULL_SCOPES

        if self.role == Role.EDITOR:
            return WRITE_SCOPES

        return DEFAULT_SCOPES
