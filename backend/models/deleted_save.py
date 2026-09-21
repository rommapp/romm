from __future__ import annotations

from datetime import datetime

from sqlalchemy import TIMESTAMP, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from models.assets import SAVE_SLOT_MAX_LENGTH
from models.base import BaseModel


class DeletedSave(BaseModel):
    """A slot emptied by its owner, so a device still holding it can be told.

    Deleting a save takes its row and its `device_save_sync` pairings with it,
    leaving a negotiation unable to tell a save nobody ever uploaded from one
    somebody removed on purpose.
    """

    __tablename__ = "deleted_saves"
    __table_args__ = (
        # One row per slot: a slot can be emptied, refilled and emptied again,
        # and only the last time decides anything.
        Index(
            "ix_deleted_saves_user_rom_slot", "user_id", "rom_id", "slot", unique=True
        ),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    rom_id: Mapped[int] = mapped_column(
        ForeignKey("roms.id", ondelete="CASCADE"), index=True
    )
    slot: Mapped[str] = mapped_column(String(length=SAVE_SLOT_MAX_LENGTH))
    # What the slot held, so a device carrying exactly those bytes is told to
    # drop them however the two clocks compare.
    content_hash: Mapped[str | None] = mapped_column(String(length=32))
    deleted_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
