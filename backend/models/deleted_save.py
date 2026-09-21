from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, TIMESTAMP, ForeignKey, Index, String
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
    # Every version the slot has held and lost, so a device carrying any of
    # them is told to drop it. Identity rather than time: the two clocks are
    # not comparable, and a device running slow would otherwise be told to
    # delete progress it made after the deletion.
    content_hashes: Mapped[list] = mapped_column(JSON, default=list)
    # For reading a row, not for deciding anything.
    deleted_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
