from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.sync_session import SyncSession, SyncSessionStatus

from .base_handler import DBBaseHandler


class DBSyncSessionsHandler(DBBaseHandler):
    @begin_session
    def create_session(
        self,
        device_id: str,
        user_id: int,
        session: Session = None,  # type: ignore
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
        session: Session = None,  # type: ignore
    ) -> SyncSession | None:
        return session.scalar(
            select(SyncSession).filter_by(id=session_id, user_id=user_id).limit(1)
        )

    @begin_session
    def get_active_session(
        self,
        device_id: str,
        user_id: int,
        session: Session = None,  # type: ignore
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
        data: dict,
        session: Session = None,  # type: ignore
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
        session: Session = None,  # type: ignore
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
        session: Session = None,  # type: ignore
    ) -> SyncSession:
        session.execute(
            update(SyncSession)
            .where(SyncSession.id == session_id)
            .values(
                status=SyncSessionStatus.COMPLETED,
                completed_at=datetime.now(timezone.utc),
                operations_completed=operations_completed,
                operations_failed=operations_failed,
            )
            .execution_options(synchronize_session="evaluate")
        )
        result = session.scalar(select(SyncSession).filter_by(id=session_id))
        if not result:
            raise NoResultFound(f"SyncSession {session_id} not found after complete")
        return result

    @begin_session
    def fail_session(
        self,
        session_id: int,
        error_message: str | None = None,
        session: Session = None,  # type: ignore
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
    def cancel_active_sessions(
        self,
        device_id: str,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> int:
        """Cancel all active sessions for a device. Returns count of cancelled sessions."""
        result = session.execute(
            update(SyncSession)
            .where(
                SyncSession.device_id == device_id,
                SyncSession.user_id == user_id,
                SyncSession.status.in_(
                    [
                        SyncSessionStatus.PENDING,
                        SyncSessionStatus.IN_PROGRESS,
                    ]
                ),
            )
            .values(
                status=SyncSessionStatus.CANCELLED,
                completed_at=datetime.now(timezone.utc),
            )
            .execution_options(synchronize_session="evaluate")
        )
        return result.rowcount

    @begin_session
    def get_sessions(
        self,
        user_id: int,
        device_id: str | None = None,
        status: SyncSessionStatus | None = None,
        limit: int = 50,
        session: Session = None,  # type: ignore
    ) -> Sequence[SyncSession]:
        query = select(SyncSession).filter_by(user_id=user_id)

        if device_id:
            query = query.filter_by(device_id=device_id)

        if status:
            query = query.filter_by(status=status)

        query = query.order_by(SyncSession.initiated_at.desc()).limit(limit)
        return session.scalars(query).all()
