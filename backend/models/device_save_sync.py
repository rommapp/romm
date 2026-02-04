from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import TIMESTAMP, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel

if TYPE_CHECKING:
    from models.assets import Save
    from models.device import Device


class DeviceSaveSync(BaseModel):
    __tablename__ = "device_save_sync"
    __table_args__ = {"extend_existing": True}

    device_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("devices.id", ondelete="CASCADE"),
        primary_key=True,
    )
    save_id: Mapped[int] = mapped_column(
        ForeignKey("saves.id", ondelete="CASCADE"),
        primary_key=True,
    )

    last_synced_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    is_untracked: Mapped[bool] = mapped_column(Boolean, default=False)

    device: Mapped[Device] = relationship(back_populates="save_syncs", lazy="raise")
    save: Mapped[Save] = relationship(back_populates="device_syncs", lazy="raise")
