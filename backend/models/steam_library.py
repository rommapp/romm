from __future__ import annotations

from datetime import datetime

from sqlalchemy import TIMESTAMP, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import BaseModel


class SteamLibraryEntry(BaseModel):
    """A game a user owns on Steam, linked to the rom that represents it."""

    __tablename__ = "steam_library_entries"
    __table_args__ = (
        UniqueConstraint("user_id", "steam_app_id", name="unique_steam_library_entry"),
        Index("ix_steam_library_entries_rom_id", "rom_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    rom_id: Mapped[int] = mapped_column(ForeignKey("roms.id", ondelete="CASCADE"))
    steam_app_id: Mapped[int] = mapped_column(Integer())
    playtime_minutes: Mapped[int] = mapped_column(Integer(), default=0)
    last_played_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), default=None
    )
