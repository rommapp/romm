import enum
from sqlalchemy import Column, String, Boolean, Integer, Enum
from starlette.authentication import SimpleUser

from .base import BaseModel


class Role(enum.Enum):
    VIEWER = 0
    EDITOR = 1
    ADMIN = 2


VIEWER_SCOPES = ["me.read", "me.write", "roms.read", "platforms.read"]
EDITOR_SCOPES = VIEWER_SCOPES + ["roms.write", "platforms.write"]
ADMIN_SCOPES = EDITOR_SCOPES + ["users.read", "users.write"]


class User(BaseModel, SimpleUser):
    __tablename__ = "users"
    id = Column(Integer(), primary_key=True, autoincrement=True)
    username: str = Column(String(length=255), unique=True, index=True)
    hashed_password: str = Column(String(length=255))
    disabled: bool = Column(Boolean(), default=False)
    role: Role = Column(Enum(Role), default=Role.ADMIN)

    @property
    def oauth_scopes(self):
        if self.role == Role.ADMIN:
            return ADMIN_SCOPES

        if self.role == Role.EDITOR:
            return EDITOR_SCOPES

        return VIEWER_SCOPES
