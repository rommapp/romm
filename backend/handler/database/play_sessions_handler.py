from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.play_session import PlaySession

from .base_handler import DBBaseHandler


class DBPlaySessionsHandler(DBBaseHandler):
    @begin_session
    def add_sessions(
        self,
        play_sessions: list[PlaySession],
        session: Session = None,  # type: ignore
    ) -> list[PlaySession]:
        session.add_all(play_sessions)
        session.flush()
        return play_sessions

    @begin_session
    def find_existing(
        self,
        user_id: int,
        device_id: str | None,
        rom_start_pairs: list[tuple[int | None, datetime]],
        session: Session = None,  # type: ignore
    ) -> set[tuple[int | None, datetime]]:
        """Return which (rom_id, start_time) pairs already exist for this user+device."""
        if not rom_start_pairs:
            return set()

        device_clause = (
            PlaySession.device_id.is_(None)
            if device_id is None
            else PlaySession.device_id == device_id
        )

        rom_clauses = []
        for rom_id, start_time in rom_start_pairs:
            rom_match = (
                PlaySession.rom_id.is_(None)
                if rom_id is None
                else PlaySession.rom_id == rom_id
            )
            rom_clauses.append(and_(rom_match, PlaySession.start_time == start_time))

        stmt = select(
            PlaySession.rom_id,
            PlaySession.start_time,
        ).where(PlaySession.user_id == user_id, device_clause, or_(*rom_clauses))

        return {
            (
                r.rom_id,
                (
                    r.start_time.replace(tzinfo=timezone.utc)
                    if r.start_time.tzinfo is None
                    else r.start_time
                ),
            )
            for r in session.execute(stmt).all()
        }

    @begin_session
    def get_sessions(
        self,
        user_id: int,
        rom_id: int | None = None,
        device_id: str | None = None,
        start_after: datetime | None = None,
        end_before: datetime | None = None,
        limit: int | None = 50,
        offset: int = 0,
        session: Session = None,  # type: ignore
    ) -> Sequence[PlaySession]:
        stmt = select(PlaySession).filter_by(user_id=user_id)

        if rom_id is not None:
            stmt = stmt.filter_by(rom_id=rom_id)
        if device_id is not None:
            stmt = stmt.filter_by(device_id=device_id)
        if start_after is not None:
            stmt = stmt.where(PlaySession.start_time >= start_after)
        if end_before is not None:
            stmt = stmt.where(PlaySession.start_time <= end_before)

        stmt = stmt.order_by(PlaySession.start_time.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        stmt = stmt.offset(offset)
        return session.scalars(stmt).all()

    @begin_session
    def get_total_play_time(
        self,
        user_id: int,
        rom_id: int,
        session: Session = None,  # type: ignore
    ) -> int:
        result = session.scalar(
            select(func.sum(PlaySession.duration_ms)).where(
                PlaySession.user_id == user_id,
                PlaySession.rom_id == rom_id,
            )
        )
        return result or 0

    @begin_session
    def delete_session(
        self,
        session_id: int,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> bool:
        result = session.execute(
            delete(PlaySession)
            .where(PlaySession.id == session_id, PlaySession.user_id == user_id)
            .execution_options(synchronize_session="evaluate")
        )
        return result.rowcount > 0
