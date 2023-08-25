import enum
from sqlalchemy import Column, String, Boolean, Integer, Enum
from starlette.authentication import SimpleUser

from .base import BaseModel
from utils.oauth import DEFAULT_SCOPES, WRITE_SCOPES, FULL_SCOPES


class Role(enum.Enum):
    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"


class User(BaseModel, SimpleUser):
    __tablename__ = "users"
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
