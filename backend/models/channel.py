from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import FILE_NAME_MAX_LENGTH, BaseModel
from models.rom import ROM_SHA1_MAX_LENGTH

if TYPE_CHECKING:
    from models.snapshot import Snapshot
    from models.user import User

CHANNEL_LABEL_MAX_LENGTH = 255
DEFAULT_CHANNEL_LABEL = "default"


class Channel(BaseModel):
    """A playthrough of one ROM file: a mutable pointer to its current snapshot."""

    __tablename__ = "channels"
    __table_args__ = (
        Index("ix_channels_user_rom", "user_id", "rom_id"),
        Index("ix_channels_rom_id", "rom_id"),
        Index("ix_channels_platform_file_hash", "platform_id", "target_file_hash"),
        Index(
            "ix_channels_platform_file_name",
            "platform_id",
            "target_file_name",
            "target_file_size",
        ),
        Index("ix_channels_current_snapshot_id", "current_snapshot_id"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid7)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    rom_id: Mapped[int | None] = mapped_column(
        ForeignKey("roms.id", ondelete="SET NULL"), default=None
    )
    platform_id: Mapped[int | None] = mapped_column(
        ForeignKey("platforms.id", ondelete="SET NULL"), default=None
    )
    target_file_hash: Mapped[str | None] = mapped_column(
        String(length=ROM_SHA1_MAX_LENGTH), default=None
    )
    target_file_name: Mapped[str] = mapped_column(String(length=FILE_NAME_MAX_LENGTH))
    target_file_size: Mapped[int] = mapped_column(BigInteger())
    label: Mapped[str] = mapped_column(String(length=CHANNEL_LABEL_MAX_LENGTH))
    current_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "snapshots.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_channels_current_snapshot_id",
        ),
        default=None,
    )
    is_hardcore: Mapped[bool] = mapped_column(default=False)
    is_public: Mapped[bool] = mapped_column(default=False)

    user: Mapped[User] = relationship(lazy="raise")
    current_snapshot: Mapped[Snapshot | None] = relationship(
        foreign_keys=[current_snapshot_id], lazy="raise", post_update=True
    )
