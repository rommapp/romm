from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from models.base import BaseModel
from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from starlette.authentication import SimpleUser

if TYPE_CHECKING:
    from handler.auth.base_handler import Scope
    from models.assets import Save, Screenshot, State
    from models.collection import Collection
    from models.rom import RomUser


class Role(enum.Enum):
    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"


class User(BaseModel, SimpleUser):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    username: Mapped[str] = mapped_column(String(length=255), unique=True, index=True)
    hashed_password: Mapped[str | None] = mapped_column(String(length=255))
    email: Mapped[str | None] = mapped_column(
        String(length=255), unique=True, index=True
    )
    enabled: Mapped[bool] = mapped_column(default=True)
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.VIEWER)
    avatar_path: Mapped[str] = mapped_column(String(length=255), default="")
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_active: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    saves: Mapped[list[Save]] = relationship(back_populates="user")
    states: Mapped[list[State]] = relationship(back_populates="user")
    screenshots: Mapped[list[Screenshot]] = relationship(back_populates="user")
    rom_users: Mapped[list[RomUser]] = relationship(back_populates="user")
    collections: Mapped[list[Collection]] = relationship(back_populates="user")

    @property
    def oauth_scopes(self) -> list[Scope]:
        from handler.auth.base_handler import DEFAULT_SCOPES, FULL_SCOPES, WRITE_SCOPES

        if self.role == Role.ADMIN:
            return FULL_SCOPES

        if self.role == Role.EDITOR:
            return WRITE_SCOPES

        return DEFAULT_SCOPES

    @property
    def fs_safe_folder_name(self):
        # Uses the ID to avoid issues with username changes
        return f"User:{self.id}".encode().hex()

    def set_last_active(self):
        from handler.database import db_user_handler

        db_user_handler.update_user(
            self.id, {"last_active": datetime.now(timezone.utc)}
        )
