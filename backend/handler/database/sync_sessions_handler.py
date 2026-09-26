from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.sync_session import SyncSession, SyncSessionStatus

from .base_handler import DBBaseHandler, affected_rows

# What a session nobody ever closed is recorded as. Sessions are opened by
# clients and by the server's own workers alike, so this names neither.
STALE_SESSION_MESSAGE = "No completion was reported before this session expired"


class DBSyncSessionsHandler(DBBaseHandler):
    @begin_session
    def create_session(
        self,
        device_id: str,
        user_id: int,
        session: Session = None,  # type: ignore[assignment]
    ) -> SyncSession:
        sync_session = SyncSession(
            device_id=device_id,
            user_id=user_id,
            status=SyncSessionStatus.PENDING,
            initiated_at=datetime.now(timezone.utc),
        )
        session.add(sync_session)
        session.flush()
        return sync_session

    @begin_session
    def get_session(
        self,
        session_id: int,
        user_id: int,
        session: Session = None,  # type: ignore[assignment]
    ) -> SyncSession | None:
        return session.scalar(
            select(SyncSession).filter_by(id=session_id, user_id=user_id).limit(1)
        )

    @begin_session
    def get_active_session(
        self,
        device_id: str,
        user_id: int,
        session: Session = None,  # type: ignore[assignment]
    ) -> SyncSession | None:
        return session.scalar(
            select(SyncSession)
            .filter(
                SyncSession.device_id == device_id,
                SyncSession.user_id == user_id,
                SyncSession.status.in_(
                    [
                        SyncSessionStatus.PENDING,
                        SyncSessionStatus.IN_PROGRESS,
                    ]
                ),
            )
            .order_by(SyncSession.initiated_at.desc())
            .limit(1)
        )

    @begin_session
    def update_session(
        self,
        session_id: int,
        data: dict[str, Any],
        session: Session = None,  # type: ignore[assignment]
    ) -> SyncSession:
        session.execute(
            update(SyncSession)
            .where(SyncSession.id == session_id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )
        result = session.scalar(select(SyncSession).filter_by(id=session_id))
        if not result:
            raise NoResultFound(f"SyncSession {session_id} not found after update")
        return result

    @begin_session
    def increment_operations_completed(
        self,
        session_id: int,
        user_id: int,
        session: Session = None,  # type: ignore[assignment]
    ) -> None:
        session.execute(
            update(SyncSession)
            .where(SyncSession.id == session_id, SyncSession.user_id == user_id)
            .values(
                operations_completed=SyncSession.operations_completed + 1,
            )
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def complete_session(
        self,
        session_id: int,
        operations_completed: int = 0,
        operations_failed: int = 0,
        session: Session = None,  # type: ignore[assignment]
    ) -> SyncSession | None:
        """Complete a session that is still open, or that the cleanup expired.

        Args:
            session_id: The session to close.
            operations_completed: How many operations its owner finished.
            operations_failed: How many it could not.

        Returns:
            The completed session, or None when it was already closed.
        """
        # Decided in the statement rather than before it, so a completion and
        # the cleanup landing together cannot both win. The cleanup's own
        # failure is the one closed state a completion may reopen: it says
        # nobody reported this, and somebody just has. A session cancelled, or
        # failed by whatever ran it, was closed on purpose.
        updated = affected_rows(
            session.execute(
                update(SyncSession)
                .where(
                    SyncSession.id == session_id,
                    or_(
                        SyncSession.status.in_(
                            [SyncSessionStatus.PENDING, SyncSessionStatus.IN_PROGRESS]
                        ),
                        and_(
                            SyncSession.status == SyncSessionStatus.FAILED,
                            SyncSession.error_message == STALE_SESSION_MESSAGE,
                        ),
                    ),
                )
                .values(
                    status=SyncSessionStatus.COMPLETED,
                    completed_at=datetime.now(timezone.utc),
                    operations_completed=operations_completed,
                    operations_failed=operations_failed,
                    # A session the cleanup gave up on, then closed by its owner,
                    # is a completed session rather than one still carrying why it
                    # was given up on.
                    error_message=None,
                )
                .execution_options(synchronize_session="evaluate")
            )
        )
        result = session.scalar(select(SyncSession).filter_by(id=session_id))
        if not result:
            raise NoResultFound(f"SyncSession {session_id} not found after complete")
        return result if updated else None

    @begin_session
    def fail_session(
        self,
        session_id: int,
        error_message: str | None = None,
        session: Session = None,  # type: ignore[assignment]
    ) -> SyncSession:
        session.execute(
            update(SyncSession)
            .where(SyncSession.id == session_id)
            .values(
                status=SyncSessionStatus.FAILED,
                completed_at=datetime.now(timezone.utc),
                error_message=error_message,
            )
            .execution_options(synchronize_session="evaluate")
        )
        result = session.scalar(select(SyncSession).filter_by(id=session_id))
        if not result:
            raise NoResultFound(f"SyncSession {session_id} not found after fail")
        return result

    @begin_session
    def fail_stale_sessions(
        self,
        older_than: datetime,
        session: Session = None,  # type: ignore[assignment]
    ) -> int:
        """Fail every session opened before ``older_than`` and never closed.

        Args:
            older_than: The moment a session still open is past accounting for.

        Returns:
            How many rows were failed.
        """
        result = session.execute(
            update(SyncSession)
            .where(
                SyncSession.initiated_at < older_than,
                SyncSession.status.in_(
                    [
                        SyncSessionStatus.PENDING,
                        SyncSessionStatus.IN_PROGRESS,
                    ]
                ),
            )
            .values(
                status=SyncSessionStatus.FAILED,
                completed_at=datetime.now(timezone.utc),
                error_message=STALE_SESSION_MESSAGE,
            )
            .execution_options(synchronize_session="evaluate")
        )
        return affected_rows(result)

    @begin_session
    def get_sessions(
        self,
        user_id: int,
        device_id: str | None = None,
        status: SyncSessionStatus | None = None,
        limit: int = 50,
        session: Session = None,  # type: ignore[assignment]
    ) -> Sequence[SyncSession]:
        query = select(SyncSession).filter_by(user_id=user_id)

        if device_id:
            query = query.filter_by(device_id=device_id)

        if status:
            query = query.filter_by(status=status)

        query = query.order_by(SyncSession.initiated_at.desc()).limit(limit)
        return session.scalars(query).all()
