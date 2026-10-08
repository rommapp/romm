from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import TIMESTAMP, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel

if TYPE_CHECKING:
    from models.channel import Channel
    from models.device import Device


class DeviceChannelSync(BaseModel):
    """The snapshot a device last pushed or applied in a channel, for attribution."""

    __tablename__ = "device_channel_sync"
    __table_args__ = (
        Index("ix_device_channel_sync_channel_id", "channel_id"),
        Index("ix_device_channel_sync_base_snapshot_id", "base_snapshot_id"),
        Index("ix_device_channel_sync_latest_known_id", "latest_known_id"),
        {"extend_existing": True},
    )

    device_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("devices.id", ondelete="CASCADE"),
        primary_key=True,
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        ForeignKey("channels.id", ondelete="CASCADE"),
        primary_key=True,
    )
    base_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("snapshots.id", ondelete="SET NULL"), default=None
    )
    synced_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    # The channel's current when the device last listed it, pushed or downloaded.
    latest_known_id: Mapped[int | None] = mapped_column(
        ForeignKey("snapshots.id", ondelete="SET NULL"), default=None
    )

    device: Mapped[Device] = relationship(lazy="raise")
    channel: Mapped[Channel] = relationship(lazy="raise")
