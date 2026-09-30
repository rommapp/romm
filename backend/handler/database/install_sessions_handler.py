from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.install_session import (
    ACTIVE_INSTALL_STATES,
    RUNNING_INSTALL_STATES,
    InstallSession,
    InstallSessionState,
)

from .base_handler import DBBaseHandler


class DBInstallSessionsHandler(DBBaseHandler):
    @begin_session
    def add_session(
        self,
        install_session: InstallSession,
        session: Session = None,  # type: ignore
    ) -> InstallSession:
        session.add(install_session)
        session.flush()
        session.refresh(install_session)
        return install_session

    @begin_session
    def get_session(
        self,
        install_session_id: int,
        session: Session = None,  # type: ignore
    ) -> InstallSession | None:
        return session.get(InstallSession, install_session_id)

    @begin_session
    def get_latest_session_for_rom(
        self,
        rom_id: int,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> InstallSession | None:
        return session.scalars(
            select(InstallSession)
            .where(
                InstallSession.rom_id == rom_id,
                InstallSession.user_id == user_id,
            )
            .order_by(InstallSession.created_at.desc(), InstallSession.id.desc())
        ).first()

    @begin_session
    def count_active_sessions(
        self,
        session: Session = None,  # type: ignore
    ) -> int:
        return len(
            session.scalars(
                select(InstallSession.id).where(
                    InstallSession.state.in_(ACTIVE_INSTALL_STATES)
                )
            ).all()
        )

    @begin_session
    def count_running_sessions(
        self,
        session: Session = None,  # type: ignore
    ) -> int:
        """Count sessions actually holding sandbox/VNC resources right now.

        Narrower than ``count_active_sessions``: DETECTING/AWAITING_INSTALLER
        don't spin up Xvfb/bwrap, so they don't count against the concurrency
        cap used to bound CPU/RAM/port usage.
        """
        return (
            session.scalar(
                select(func.count(InstallSession.id)).where(
                    InstallSession.state.in_(RUNNING_INSTALL_STATES)
                )
            )
            or 0
        )

    @begin_session
    def get_running_session_for_user_port(
        self,
        user_id: int,
        vnc_web_port: int,
        session: Session = None,  # type: ignore
    ) -> InstallSession | None:
        """Session this user owns whose sandbox is currently on this VNC port.

        Backs the nginx ``auth_request`` gate on the VNC proxy: only the user
        who started the install may reach its display.
        """
        return session.scalars(
            select(InstallSession).where(
                InstallSession.user_id == user_id,
                InstallSession.vnc_web_port == vnc_web_port,
                InstallSession.state == InstallSessionState.INSTALLING,
            )
        ).first()

    @begin_session
    def update_session(
        self,
        install_session_id: int,
        data: dict,
        session: Session = None,  # type: ignore
    ) -> InstallSession | None:
        session.execute(
            update(InstallSession)
            .where(InstallSession.id == install_session_id)
            .values(**data)
        )
        return session.get(InstallSession, install_session_id)

    @begin_session
    def delete_session(
        self,
        install_session_id: int,
        session: Session = None,  # type: ignore
    ) -> None:
        session.execute(
            delete(InstallSession).where(InstallSession.id == install_session_id)
        )

    @begin_session
    def get_dashboard_sessions_for_user(
        self,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> list[InstallSession]:
        """A user's install sessions worth surfacing on the dashboard.

        One row per ROM (its most recent session), limited to sessions that
        are either still active or finished with a cache still on disk
        (DONE) - a FAILED/EXPIRED session with nothing left to show or
        resume isn't dashboard material. Backs the "Active Installers" Home
        widget, which only renders when this list is non-empty.
        """
        latest_per_rom = (
            select(
                InstallSession.id,
                func.row_number()
                .over(
                    partition_by=InstallSession.rom_id,
                    # id as a tiebreaker: two sessions for the same ROM can
                    # share a created_at (column resolution, or just two
                    # fast inserts), and ORDER BY alone is then ambiguous
                    # about which row_number() calls "latest".
                    order_by=(
                        InstallSession.created_at.desc(),
                        InstallSession.id.desc(),
                    ),
                )
                .label("rank"),
            )
            .where(InstallSession.user_id == user_id)
            .subquery()
        )
        latest_ids = select(latest_per_rom.c.id).where(latest_per_rom.c.rank == 1)
        return list(
            session.scalars(
                select(InstallSession)
                .where(
                    InstallSession.id.in_(latest_ids),
                    InstallSession.state.in_(
                        {*ACTIVE_INSTALL_STATES, InstallSessionState.DONE}
                    ),
                )
                .order_by(InstallSession.updated_at.desc())
            ).all()
        )

    @begin_session
    def get_sessions_for_rom(
        self,
        rom_id: int,
        session: Session = None,  # type: ignore
    ) -> list[InstallSession]:
        return list(
            session.scalars(
                select(InstallSession).where(InstallSession.rom_id == rom_id)
            ).all()
        )

    @begin_session
    def get_all_sessions(
        self,
        session: Session = None,  # type: ignore
    ) -> list[InstallSession]:
        return list(
            session.scalars(
                select(InstallSession).order_by(InstallSession.created_at.desc())
            ).all()
        )

    @begin_session
    def get_expired_sessions(
        self,
        session: Session = None,  # type: ignore
    ) -> list[InstallSession]:
        """Sessions whose TTL has elapsed (unlimited sessions are never
        returned). A session still actively running is excluded even past
        its TTL - evicting its cache out from under the worker would corrupt
        a write in progress; it becomes eligible once it leaves
        RUNNING_INSTALL_STATES."""
        now = datetime.now(timezone.utc)
        return list(
            session.scalars(
                select(InstallSession).where(
                    InstallSession.expires_at.is_not(None),
                    InstallSession.expires_at < now,
                    InstallSession.state != InstallSessionState.EXPIRED,
                    InstallSession.state.not_in(RUNNING_INSTALL_STATES),
                )
            ).all()
        )
