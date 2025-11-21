from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import TIMESTAMP, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from starlette.authentication import SimpleUser

from config import KIOSK_MODE
from handler.auth.constants import (
    EDIT_SCOPES,
    FULL_SCOPES,
    READ_SCOPES,
    WRITE_SCOPES,
    Scope,
)
from models.base import BaseModel
from utils.database import CustomJSON

if TYPE_CHECKING:
    from models.assets import Save, Screenshot, State
    from models.collection import Collection, SmartCollection
    from models.rom import RomNote, RomUser


class Role(enum.Enum):
    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"


TEXT_FIELD_LENGTH = 255


class User(BaseModel, SimpleUser):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    username: Mapped[str] = mapped_column(
        String(length=TEXT_FIELD_LENGTH), unique=True, index=True
    )
    hashed_password: Mapped[str | None] = mapped_column(
        String(length=TEXT_FIELD_LENGTH)
    )
    email: Mapped[str | None] = mapped_column(
        String(length=TEXT_FIELD_LENGTH), unique=True, index=True
    )
    enabled: Mapped[bool] = mapped_column(default=True)
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.VIEWER)
    avatar_path: Mapped[str] = mapped_column(
        String(length=TEXT_FIELD_LENGTH), default=""
    )
    last_login: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_active: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    ra_username: Mapped[str | None] = mapped_column(
        String(length=TEXT_FIELD_LENGTH), default=""
    )
    ra_progression: Mapped[dict[str, Any] | None] = mapped_column(
        CustomJSON(), default=dict
    )

    saves: Mapped[list[Save]] = relationship(lazy="raise", back_populates="user")
    states: Mapped[list[State]] = relationship(lazy="raise", back_populates="user")
    screenshots: Mapped[list[Screenshot]] = relationship(
        lazy="raise", back_populates="user"
    )
    rom_users: Mapped[list[RomUser]] = relationship(lazy="raise", back_populates="user")
    notes: Mapped[list[RomNote]] = relationship(lazy="raise", back_populates="user")
    collections: Mapped[list[Collection]] = relationship(
        lazy="raise", back_populates="user"
    )
    smart_collections: Mapped[list["SmartCollection"]] = relationship(
        lazy="raise", back_populates="user"
    )

    @classmethod
    def kiosk_mode_user(cls) -> User:
        now = datetime.now(timezone.utc)
        return cls(
            id=-1,
            username="kiosk",
            role=Role.VIEWER,
            enabled=True,
            avatar_path="",
            last_active=now,
            last_login=now,
            created_at=now,
            updated_at=now,
        )

    @property
    def oauth_scopes(self) -> list[Scope]:
        if self.role == Role.ADMIN:
            return FULL_SCOPES

        if self.role == Role.EDITOR:
            return EDIT_SCOPES

        if KIOSK_MODE:
            return READ_SCOPES

        return WRITE_SCOPES

    @property
    def fs_safe_folder_name(self):
        # Uses the ID to avoid issues with username changes
        return f"User:{self.id}".encode().hex()

    def set_last_active(self):
        from handler.database import db_user_handler

        db_user_handler.update_user(
            self.id, {"last_active": datetime.now(timezone.utc)}
        )
