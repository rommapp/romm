from __future__ import annotations

import enum
from datetime import datetime
from typing import Final

from sqlalchemy import TIMESTAMP, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import BaseModel
from utils.database import CustomJSON


class NotificationChannelType(enum.StrEnum):
    # Any service Apprise reaches, set up through that service's own fields.
    APPRISE = "apprise"
    # RomM's own JSON payload, signed when the channel has a secret.
    WEBHOOK = "webhook"
    EMAIL = "email"


class NotificationChannelMinLevel(enum.StrEnum):
    """The least severe notification a channel forwards; success ranks as info."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


NOTIFICATION_CHANNEL_NAME_MAX_LENGTH: Final = 100
NOTIFICATION_CHANNEL_URL_MAX_LENGTH: Final = 2000
NOTIFICATION_CHANNEL_SECRET_MAX_LENGTH: Final = 255
NOTIFICATION_CHANNEL_ERROR_MAX_LENGTH: Final = 1000
NOTIFICATION_CHANNEL_ADDRESS_MAX_LENGTH: Final = 320
NOTIFICATION_CHANNEL_CODE_MAX_LENGTH: Final = 16
NOTIFICATION_CHANNEL_SERVICE_MAX_LENGTH: Final = 32
NOTIFICATION_CHANNEL_MAX_FIELDS: Final = 64
# Each target of a list is its own request to the service.
NOTIFICATION_CHANNEL_MAX_LIST_ITEMS: Final = 20
MAX_NOTIFICATION_CHANNELS_PER_USER: Final = 20
# A channel that fails this many deliveries in a row turns itself off.
MAX_CONSECUTIVE_DELIVERY_FAILURES: Final = 10


class NotificationChannel(BaseModel):
    __tablename__ = "notification_channels"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(NOTIFICATION_CHANNEL_NAME_MAX_LENGTH))
    # Sealed with `utils.secret_box`: a URL can carry its own token.
    config: Mapped[str] = mapped_column(Text)
    min_level: Mapped[str] = mapped_column(String(16), default="info")
    # None forwards every topic.
    topics: Mapped[list[str] | None] = mapped_column(CustomJSON(), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # An email address proves it belongs to the user with a code first.
    confirmed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    last_delivered_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(
        String(NOTIFICATION_CHANNEL_ERROR_MAX_LENGTH), nullable=True
    )
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
