from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel

if TYPE_CHECKING:
    from models.device import Device
    from models.rom import Rom
    from models.sync_session import SyncSession
    from models.user import User


class PlaySession(BaseModel):
    __tablename__ = "play_sessions"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "device_id",
            "rom_id",
            "start_time",
            name="uq_play_session_identity",
        ),
        Index("ix_play_sessions_user_rom", "user_id", "rom_id"),
        Index("ix_play_sessions_user_time", "user_id", "start_time"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    device_id: Mapped[str | None] = mapped_column(
        String(255), ForeignKey("devices.id", ondelete="SET NULL")
    )
    rom_id: Mapped[int | None] = mapped_column(
        ForeignKey("roms.id", ondelete="SET NULL")
    )
    sync_session_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sync_sessions.id", ondelete="SET NULL"), default=None
    )
    save_slot: Mapped[str | None] = mapped_column(String(255), default=None)
    start_time: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    end_time: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    duration_ms: Mapped[int] = mapped_column(BigInteger())

    user: Mapped[User] = relationship(lazy="raise", back_populates="play_sessions")
    device: Mapped[Device | None] = relationship(lazy="raise")
    rom: Mapped[Rom | None] = relationship(lazy="raise")
    sync_session: Mapped[SyncSession | None] = relationship(lazy="raise")
