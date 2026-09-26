from __future__ import annotations

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from models.assets import SAVE_SLOT_MAX_LENGTH
from models.base import BaseModel
from utils.database import CustomJSON, ExactString

# Trimming drops the oldest, which a long-offline device is likeliest to hold;
# past the bound that device is answered `upload` rather than `delete`.
MAX_REMEMBERED_HASHES = 100


class DeletedAsset(BaseModel):
    """A slot emptied by its owner, so a device still holding it can be told."""

    __tablename__ = "deleted_assets"
    __table_args__ = (
        # One row per slot, however often it is emptied and refilled.
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
    # Every version the slot lost, matched by identity rather than by time:
    # a device's clock is not the server's.
    content_hashes: Mapped[list[str]] = mapped_column(CustomJSON(), default=list)
