from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.notification import Notification

from .base_handler import DBBaseHandler, affected_rows

# A user who never clears their inbox keeps only this many, newest first.
MAX_NOTIFICATIONS_PER_USER = 200


class DBNotificationsHandler(DBBaseHandler):
    @begin_session
    def add_notification(
        self,
        notification: Notification,
        session: Session = None,  # type: ignore
    ) -> Notification:
        session.add(notification)
        session.flush()

        overflow = (
            select(Notification.id)
            .where(Notification.user_id == notification.user_id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset(MAX_NOTIFICATIONS_PER_USER)
        )
        stale_ids = session.scalars(overflow).all()
        if stale_ids:
            session.execute(
                delete(Notification)
                .where(Notification.id.in_(stale_ids))
                .execution_options(synchronize_session=False)
            )

        session.refresh(notification)
        return notification

    @begin_session
    def get_notifications(
        self,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> Sequence[Notification]:
        return session.scalars(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
        ).all()

    @begin_session
    def mark_read(
        self,
        user_id: int,
        ids: list[int] | None = None,
        session: Session = None,  # type: ignore
    ) -> int:
        """Mark the user's unread notifications read, all of them when `ids` is None."""
        stmt = update(Notification).where(
            Notification.user_id == user_id, Notification.read_at.is_(None)
        )
        if ids is not None:
            stmt = stmt.where(Notification.id.in_(ids))

        result = session.execute(
            stmt.values(read_at=datetime.now(timezone.utc)).execution_options(
                synchronize_session=False
            )
        )
        return affected_rows(result)

    @begin_session
    def delete_notifications(
        self,
        user_id: int,
        ids: list[int] | None = None,
        session: Session = None,  # type: ignore
    ) -> int:
        """Delete the user's notifications, all of them when `ids` is None."""
        stmt = delete(Notification).where(Notification.user_id == user_id)
        if ids is not None:
            stmt = stmt.where(Notification.id.in_(ids))

        result = session.execute(stmt.execution_options(synchronize_session=False))
        return affected_rows(result)
