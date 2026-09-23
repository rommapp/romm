from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.notification_channel import (
    MAX_CONSECUTIVE_DELIVERY_FAILURES,
    NOTIFICATION_CHANNEL_ERROR_MAX_LENGTH,
    NotificationChannel,
)
from models.user import User

from .base_handler import DBBaseHandler, affected_rows


class DBNotificationChannelsHandler(DBBaseHandler):
    @begin_session
    def get_channels(
        self,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> Sequence[NotificationChannel]:
        return session.scalars(
            select(NotificationChannel)
            .where(NotificationChannel.user_id == user_id)
            .order_by(NotificationChannel.id)
        ).all()

    @begin_session
    def get_channel(
        self,
        channel_id: int,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> NotificationChannel | None:
        return session.scalar(
            select(NotificationChannel).where(
                NotificationChannel.id == channel_id,
                NotificationChannel.user_id == user_id,
            )
        )

    @begin_session
    def count_channels(
        self,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> int:
        return (
            session.scalar(
                select(func.count())
                .select_from(NotificationChannel)
                .where(NotificationChannel.user_id == user_id)
            )
            or 0
        )

    @begin_session
    def get_channel_for_delivery(
        self,
        channel_id: int,
        session: Session = None,  # type: ignore
    ) -> tuple[NotificationChannel, str] | None:
        """The channel and its owner's role, as of now."""
        row = session.execute(
            select(NotificationChannel, User.role)
            .join(User, User.id == NotificationChannel.user_id)
            .where(NotificationChannel.id == channel_id)
        ).first()
        if row is None:
            return None
        channel, role = row
        return channel, role

    @begin_session
    def get_deliverable_channels(
        self,
        user_ids: Sequence[int],
        session: Session = None,  # type: ignore
    ) -> Sequence[NotificationChannel]:
        """The users' channels that are on and, for an email address, confirmed."""
        return session.scalars(
            select(NotificationChannel).where(
                NotificationChannel.user_id.in_(user_ids),
                NotificationChannel.enabled.is_(True),
                NotificationChannel.confirmed_at.is_not(None),
            )
        ).all()

    @begin_session
    def add_channel(
        self,
        channel: NotificationChannel,
        session: Session = None,  # type: ignore
    ) -> NotificationChannel:
        session.add(channel)
        session.flush()
        return channel

    @begin_session
    def update_channel(
        self,
        channel_id: int,
        user_id: int,
        data: dict[str, Any],
        session: Session = None,  # type: ignore
    ) -> NotificationChannel | None:
        session.execute(
            update(NotificationChannel)
            .where(
                NotificationChannel.id == channel_id,
                NotificationChannel.user_id == user_id,
            )
            .values(**data)
            .execution_options(synchronize_session=False)
        )
        return session.scalar(
            select(NotificationChannel).where(
                NotificationChannel.id == channel_id,
                NotificationChannel.user_id == user_id,
            )
        )

    @begin_session
    def delete_channel(
        self,
        channel_id: int,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> int:
        result = session.execute(
            delete(NotificationChannel)
            .where(
                NotificationChannel.id == channel_id,
                NotificationChannel.user_id == user_id,
            )
            .execution_options(synchronize_session=False)
        )
        return affected_rows(result)

    @begin_session
    def record_delivery(
        self,
        channel_id: int,
        session: Session = None,  # type: ignore
    ) -> None:
        session.execute(
            update(NotificationChannel)
            .where(NotificationChannel.id == channel_id)
            .values(
                last_delivered_at=datetime.now(timezone.utc),
                last_error=None,
                consecutive_failures=0,
            )
            .execution_options(synchronize_session=False)
        )

    @begin_session
    def record_failure(
        self,
        channel_id: int,
        error: str,
        counts: bool,
        session: Session = None,  # type: ignore
    ) -> None:
        """Keep a failed delivery's error; one that `counts` brings the channel closer to off."""
        values: dict[str, Any] = {
            "last_error": error[:NOTIFICATION_CHANNEL_ERROR_MAX_LENGTH]
        }
        if counts:
            values["consecutive_failures"] = (
                NotificationChannel.consecutive_failures + 1
            )
        session.execute(
            update(NotificationChannel)
            .where(NotificationChannel.id == channel_id)
            .values(**values)
            .execution_options(synchronize_session=False)
        )

    @begin_session
    def turn_off_if_failing(
        self,
        channel_id: int,
        session: Session = None,  # type: ignore
    ) -> bool:
        """Turn the channel off once it failed too often in a row; True if this call did."""
        result = session.execute(
            update(NotificationChannel)
            .where(
                NotificationChannel.id == channel_id,
                NotificationChannel.enabled.is_(True),
                NotificationChannel.consecutive_failures
                >= MAX_CONSECUTIVE_DELIVERY_FAILURES,
            )
            .values(enabled=False)
            .execution_options(synchronize_session=False)
        )
        return affected_rows(result) == 1
