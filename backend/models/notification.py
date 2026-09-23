from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any, Final

from sqlalchemy import TIMESTAMP, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel
from utils.database import CustomJSON

if TYPE_CHECKING:
    from models.user import User


class NotificationLevel(enum.StrEnum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class NotificationKind(enum.StrEnum):
    """What happened, translated by the client; any other kind shows its own title and body."""

    CUSTOM = "custom"
    SCAN_COMPLETED = "scan_completed"
    SCAN_FAILED = "scan_failed"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    STREAMING_SESSION_ENDED = "streaming_session_ended"
    ROLE_CHANGED = "role_changed"


# A user who never clears their inbox keeps only this many, newest first.
MAX_NOTIFICATIONS_PER_USER: Final = 200

NOTIFICATION_KIND_MAX_LENGTH: Final = 64
NOTIFICATION_TITLE_MAX_LENGTH: Final = 255
NOTIFICATION_BODY_MAX_LENGTH: Final = 1000
NOTIFICATION_LINK_MAX_LENGTH: Final = 1000
NOTIFICATION_ICON_MAX_LENGTH: Final = 64
# Of `data` serialized as JSON, for what API clients send.
NOTIFICATION_DATA_MAX_LENGTH: Final = 4096


class Notification(BaseModel):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_created", "user_id", "created_at"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # The user whose action caused it, when it wasn't a background process.
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Strings rather than database enums, so a new kind needs no migration.
    kind: Mapped[str] = mapped_column(String(NOTIFICATION_KIND_MAX_LENGTH))
    level: Mapped[str] = mapped_column(String(16))
    title: Mapped[str | None] = mapped_column(
        String(NOTIFICATION_TITLE_MAX_LENGTH), nullable=True
    )
    body: Mapped[str | None] = mapped_column(
        String(NOTIFICATION_BODY_MAX_LENGTH), nullable=True
    )
    # An in-app path (`/rom/12`), never an external URL.
    link: Mapped[str | None] = mapped_column(
        String(NOTIFICATION_LINK_MAX_LENGTH), nullable=True
    )
    icon: Mapped[str | None] = mapped_column(
        String(NOTIFICATION_ICON_MAX_LENGTH), nullable=True
    )
    # The values the kind's text is built from (names, counts, ids to link to).
    data: Mapped[dict[str, Any]] = mapped_column(CustomJSON(), default=dict)
    read_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    actor: Mapped[User | None] = relationship(lazy="raise", foreign_keys=[actor_id])
