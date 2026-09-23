from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any

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
    """What happened. The client renders the text from it, in the reader's language."""

    SCAN_COMPLETED = "scan_completed"
    SCAN_FAILED = "scan_failed"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    STREAMING_SESSION_ENDED = "streaming_session_ended"
    ROLE_CHANGED = "role_changed"


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
    kind: Mapped[str] = mapped_column(String(64))
    level: Mapped[str] = mapped_column(String(16))
    # The values the kind's text is built from (names, counts, ids to link to).
    data: Mapped[dict[str, Any] | None] = mapped_column(CustomJSON(), default=dict)
    read_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    actor: Mapped[User | None] = relationship(lazy="joined", foreign_keys=[actor_id])
