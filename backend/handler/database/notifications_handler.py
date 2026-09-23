from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, joinedload

from decorators.database import begin_session
from models.notification import MAX_NOTIFICATIONS_PER_USER, Notification
from models.user import User

from .base_handler import DBBaseHandler, affected_rows


def _with_actor():
    # Name and avatar only, the rest of a user row is large JSON. Built per query,
    # as touching `User` columns at import configures the mappers too early.
    return joinedload(Notification.actor).load_only(
        User.id, User.username, User.avatar_path, User.updated_at
    )


class DBNotificationsHandler(DBBaseHandler):
    @begin_session
    def add_notifications(
        self,
        notifications: Sequence[Notification],
        session: Session = None,  # type: ignore
    ) -> Sequence[Notification]:
        """Store notifications and trim their users' inboxes; returns the rows kept."""
        session.add_all(notifications)
        session.flush()

        for user_id in {n.user_id for n in notifications}:
            stale_ids = session.scalars(
                select(Notification.id)
                .where(Notification.user_id == user_id)
                .order_by(Notification.created_at.desc(), Notification.id.desc())
                .offset(MAX_NOTIFICATIONS_PER_USER)
            ).all()
            if stale_ids:
                session.execute(
                    delete(Notification)
                    .where(Notification.id.in_(stale_ids))
                    .execution_options(synchronize_session=False)
                )

        return session.scalars(
            select(Notification)
            .options(_with_actor())
            .where(Notification.id.in_([n.id for n in notifications]))
            .order_by(Notification.id)
        ).all()

    @begin_session
    def get_notifications(
        self,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> Sequence[Notification]:
        return session.scalars(
            select(Notification)
            .options(_with_actor())
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
