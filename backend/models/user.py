import enum

from models.base import BaseModel
from models.assets import Save, Screenshot, State
from sqlalchemy import Boolean, Column, Enum, Integer, String
from starlette.authentication import SimpleUser
from sqlalchemy.orm import Mapped, relationship


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

    saves: Mapped[list[Save]] = relationship(
        "Save",
        lazy="selectin",
        back_populates="user",
    )
    states: Mapped[list[State]] = relationship(
        "State", lazy="selectin", back_populates="user"
    )
    screenshots: Mapped[list[Screenshot]] = relationship(
        "Screenshot", lazy="selectin", back_populates="user"
    )

    @property
    def oauth_scopes(self):
        from handler.auth_handler import DEFAULT_SCOPES, FULL_SCOPES, WRITE_SCOPES

        if self.role == Role.ADMIN:
            return FULL_SCOPES

        if self.role == Role.EDITOR:
            return WRITE_SCOPES

        return DEFAULT_SCOPES
    
    @property
    def fs_safe_folder_name(self):
        # Uses the ID to avoid issues with username changes
        return f'User:{self.id}'.encode("utf-8").hex()
