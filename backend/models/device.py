from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import TIMESTAMP, Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel

if TYPE_CHECKING:
    from models.device_save_sync import DeviceSaveSync
    from models.user import User


class SyncMode(enum.StrEnum):
    API = "api"
    FILE_TRANSFER = "file_transfer"
    PUSH_PULL = "push_pull"


class Device(BaseModel):
    __tablename__ = "devices"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    name: Mapped[str | None] = mapped_column(String(255))
    platform: Mapped[str | None] = mapped_column(String(50))
    client: Mapped[str | None] = mapped_column(String(50))
    client_version: Mapped[str | None] = mapped_column(String(50))

    ip_address: Mapped[str | None] = mapped_column(String(45))
    mac_address: Mapped[str | None] = mapped_column(String(17))
    hostname: Mapped[str | None] = mapped_column(String(255))

    sync_mode: Mapped[SyncMode] = mapped_column(Enum(SyncMode), default=SyncMode.API)
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    last_seen: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    user: Mapped[User] = relationship(lazy="joined")
    save_syncs: Mapped[list[DeviceSaveSync]] = relationship(
        back_populates="device",
        cascade="all, delete-orphan",
        lazy="raise",
    )
