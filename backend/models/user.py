from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import TIMESTAMP, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from starlette.authentication import SimpleUser

from handler.auth.constants import Scope
from models.base import BaseModel
from models.permission import PermissionGroup
from utils.database import CustomJSON

if TYPE_CHECKING:
    from models.assets import Save, Screenshot, State
    from models.client_token import ClientToken
    from models.collection import Collection, SmartCollection
    from models.device import Device
    from models.play_session import PlaySession
    from models.rom import RomNote, RomUser


class Role(enum.StrEnum):
    # Two kinds only: admins bypass all permission checks; everyone else is a
    # `user` whose access comes entirely from their permission group + overrides.
    # (The old viewer/editor split was folded into groups.)
    USER = "user"
    ADMIN = "admin"

    @classmethod
    def coerce(cls, value: str | None) -> Role:
        """Map any role string to the two-value set. Only an exact ``admin``
        becomes ADMIN; everything else (``user``, the legacy ``viewer`` /
        ``editor`` from in-flight invites, unknown, empty) collapses to USER."""
        return cls.ADMIN if (value or "").strip().lower() == "admin" else cls.USER


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
    # VARCHAR-backed (native_enum=False) storing the lowercase value, so the
    # vocabulary stays portable across SQLite/MariaDB/Postgres.
    role: Mapped[Role] = mapped_column(
        Enum(
            Role,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=Role.USER,
    )
    # The granular permission group this user belongs to. NULL falls back to the
    # server-wide default group in the resolver. Admins bypass groups entirely.
    permission_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("permission_groups.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
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
    ui_settings: Mapped[dict[str, Any] | None] = mapped_column(
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
    devices: Mapped[list["Device"]] = relationship(
        lazy="raise", back_populates="user", cascade="all, delete-orphan"
    )
    client_tokens: Mapped[list["ClientToken"]] = relationship(
        lazy="raise", back_populates="user", cascade="all, delete-orphan"
    )
    play_sessions: Mapped[list["PlaySession"]] = relationship(
        lazy="raise", back_populates="user", cascade="all, delete-orphan"
    )
    # Loaded explicitly by the permission resolver; lazy="raise" keeps it off
    # every other user query so the schema-wide query shape is unchanged.
    permission_group: Mapped[PermissionGroup | None] = relationship(lazy="raise")

    @classmethod
    def kiosk_mode_user(cls) -> User:
        now = datetime.now(timezone.utc)
        return cls(
            id=-1,
            username="kiosk",
            role=Role.USER,
            enabled=True,
            avatar_path="",
            last_active=now,
            last_login=now,
            created_at=now,
            updated_at=now,
        )

    @property
    def oauth_scopes(self) -> list[Scope]:
        # Derived from the granular permission model (groups + overrides),
        # projected onto the legacy coarse scopes. Resolved per access via its
        # own session; admins short-circuit without touching the DB.
        # Local import: breaks the models.user <-> handler.auth.permissions cycle.
        from handler.auth.permissions import compute_oauth_scopes

        return compute_oauth_scopes(self)

    @property
    def fs_safe_folder_name(self):
        # Uses the ID to avoid issues with username changes
        return f"User:{self.id}".encode().hex()

    def set_last_active(self):
        from handler.database import db_user_handler

        db_user_handler.update_user(
            self.id, {"last_active": datetime.now(timezone.utc)}
        )
