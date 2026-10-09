from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.assets import EMULATOR_MAX_LENGTH
from models.base import BaseModel
from models.rom import ROM_SHA1_MAX_LENGTH, TITLE_ID_MAX_LENGTH

if TYPE_CHECKING:
    from models.assets import Save, State
    from models.channel import Channel

SNAPSHOT_DIGEST_LENGTH = 64
STATE_SLOT_MAX_LENGTH = 50


class SnapshotKind(enum.StrEnum):
    CHANNEL = "channel"
    ARCHIVAL = "archival"
    BRANCH = "branch"


class ConflictReason(enum.StrEnum):
    """Why a push into a channel was kept as a branch."""

    # The push built on the current it expected, which another write replaced.
    MOVED = "moved"
    # The push built on a snapshot older than the current it expected, which moved too.
    MOVED_FROM_OLDER = "moved_from_older"


class Snapshot(BaseModel):
    """A fixed checkpoint: an optional save plus a bank of states."""

    __tablename__ = "snapshots"
    __table_args__ = (
        Index("ix_snapshots_channel_created", "channel_id", "created_at"),
        Index("ix_snapshots_channel_digest", "channel_id", "digest"),
        Index("ix_snapshots_user_rom_kind", "user_id", "rom_id", "kind"),
        Index("ix_snapshots_author_user_id", "author_user_id"),
        Index("ix_snapshots_rom_id", "rom_id"),
        Index("ix_snapshots_parent_snapshot_id", "parent_snapshot_id"),
        Index("ix_snapshots_save_id", "save_id"),
        Index("ix_snapshots_origin_device_id", "origin_device_id"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    author_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    rom_id: Mapped[int | None] = mapped_column(
        ForeignKey("roms.id", ondelete="SET NULL"), default=None
    )
    channel_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("channels.id", ondelete="CASCADE"), default=None
    )
    parent_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("snapshots.id", ondelete="SET NULL"), default=None
    )
    kind: Mapped[SnapshotKind] = mapped_column(Enum(SnapshotKind))
    is_public: Mapped[bool] = mapped_column(default=False)
    save_id: Mapped[int | None] = mapped_column(
        ForeignKey("saves.id", ondelete="RESTRICT"), default=None
    )
    digest: Mapped[str] = mapped_column(String(length=SNAPSHOT_DIGEST_LENGTH))
    rom_sha1: Mapped[str | None] = mapped_column(
        String(length=ROM_SHA1_MAX_LENGTH), default=None
    )
    is_hardcore: Mapped[bool] = mapped_column(default=False)
    save_target: Mapped[str | None] = mapped_column(
        String(length=TITLE_ID_MAX_LENGTH), default=None
    )
    emulator: Mapped[str | None] = mapped_column(
        String(length=EMULATOR_MAX_LENGTH), default=None
    )
    origin_device_id: Mapped[str | None] = mapped_column(
        String(length=255),
        ForeignKey("devices.id", ondelete="SET NULL"),
        default=None,
    )

    channel: Mapped[Channel | None] = relationship(
        foreign_keys=[channel_id], lazy="raise"
    )
    save: Mapped[Save | None] = relationship(lazy="raise")
    states: Mapped[list[SnapshotState]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    def readable_by(self, user_id: int, channel: Channel | None) -> bool:
        """Whether a user may read this snapshot: their own, one in a shared
        channel, or a shared archival one. `channel` is the snapshot's own."""
        if self.user_id == user_id:
            return True
        if channel is not None:
            return channel.is_public
        return self.kind == SnapshotKind.ARCHIVAL and self.is_public


class SnapshotState(BaseModel):
    """One filled slot of a snapshot's bank."""

    __tablename__ = "snapshot_states"
    __table_args__ = (
        Index("ix_snapshot_states_state_id", "state_id"),
        {"extend_existing": True},
    )

    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("snapshots.id", ondelete="CASCADE"), primary_key=True
    )
    core: Mapped[str] = mapped_column(
        String(length=EMULATOR_MAX_LENGTH), primary_key=True
    )
    slot: Mapped[str] = mapped_column(
        String(length=STATE_SLOT_MAX_LENGTH), primary_key=True
    )
    state_id: Mapped[int] = mapped_column(ForeignKey("states.id", ondelete="RESTRICT"))

    snapshot: Mapped[Snapshot] = relationship(back_populates="states", lazy="raise")
    state: Mapped[State] = relationship(lazy="raise")


class SnapshotPin(BaseModel):
    """One user's pin on a snapshot, which keeps it from pruning while that
    user can read it."""

    __tablename__ = "snapshot_pins"
    __table_args__ = (
        Index("ix_snapshot_pins_user_id", "user_id"),
        {"extend_existing": True},
    )

    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("snapshots.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
