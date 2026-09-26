from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from models.assets import SAVE_SLOT_MAX_LENGTH
from models.base import BaseModel
from utils.database import CustomJSON, ExactString
from utils.datetime import to_utc

# Trimming drops the oldest, which a long-offline device is likeliest to hold;
# past the bound that device's version is negotiated as if it were new.
MAX_REMEMBERED_HASHES = 100


class DeletedAsset(BaseModel):
    """The versions a slot lost, so a device still holding one can be told."""

    __tablename__ = "deleted_assets"
    __table_args__ = (
        # One row per slot, however many versions it loses.
        Index(
            "ix_deleted_assets_user_rom_slot", "user_id", "rom_id", "slot", unique=True
        ),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    rom_id: Mapped[int] = mapped_column(
        ForeignKey("roms.id", ondelete="CASCADE"), index=True
    )
    # Exact, like `Save.slot`, so the unique index keys what negotiation looks up.
    slot: Mapped[str] = mapped_column(ExactString(SAVE_SLOT_MAX_LENGTH))
    # Every version the slot lost, oldest first, matched by what a device reports holding.
    content_hashes: Mapped[list[str]] = mapped_column(CustomJSON(), default=list)
    # When each was lost, by the server's clock: a device copy written later is new progress.
    removed_at: Mapped[dict[str, str] | None] = mapped_column(
        CustomJSON(), nullable=True, default=dict
    )

    def removal_times(self) -> dict[str, datetime]:
        """When each remembered version was lost, the record's own time where unstamped."""
        stamped = self.removed_at or {}
        return {
            content_hash: (
                to_utc(datetime.fromisoformat(stamped[content_hash]))
                if content_hash in stamped
                else to_utc(self.updated_at)
            )
            for content_hash in self.content_hashes
        }
