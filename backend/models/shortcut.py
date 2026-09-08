from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel

if TYPE_CHECKING:
    from models.device import Device
    from models.rom import Rom
    from models.user import User


class ShortcutStatus(enum.StrEnum):
    PENDING_ADD = "pending_add"
    STAGED = "staged"
    ADDED = "added"
    PENDING_REMOVE = "pending_remove"
    FAILED = "failed"


class LaunchMode(enum.StrEnum):
    EMULATOR = "emulator"
    WEB_PLAYER = "web_player"


class Shortcut(BaseModel):
    """A game a user wants in a launcher on one paired device."""

    __tablename__ = "shortcuts"
    __table_args__ = (
        UniqueConstraint("device_id", "rom_id", name="uq_shortcuts_device_rom"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[str] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    rom_id: Mapped[int] = mapped_column(
        ForeignKey("roms.id", ondelete="CASCADE"), index=True
    )

    status: Mapped[ShortcutStatus] = mapped_column(
        Enum(ShortcutStatus), default=ShortcutStatus.PENDING_ADD
    )
    launch_mode: Mapped[LaunchMode | None] = mapped_column(
        Enum(LaunchMode), nullable=True
    )
    # Steam's non-Steam app id is an unsigned 32-bit value, above int32 range.
    steam_app_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(lazy="select")
    device: Mapped[Device] = relationship(lazy="joined")
    rom: Mapped[Rom] = relationship(lazy="joined")
