from decorators.database import begin_session
from models.assets import Save, Screenshot, State
from models.platform import Platform
from models.rom import Rom
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .base_handler import DBBaseHandler


class DBStatsHandler(DBBaseHandler):
    @begin_session
    def get_platforms_count(self, session: Session = None) -> int:
        # Only count platforms with more then 0 roms
        return session.scalar(
            select(func.count())
            .select_from(Platform)
            .where(
                select(func.count())
                .select_from(Rom)
                .filter_by(platform_id=Platform.id)
                .as_scalar()
                > 0
            )
        )

    @begin_session
    def get_roms_count(self, session: Session = None) -> int:
        return session.scalar(select(func.count()).select_from(Rom))

    @begin_session
    def get_saves_count(self, session: Session = None) -> int:
        return session.scalar(select(func.count()).select_from(Save))

    @begin_session
    def get_states_count(self, session: Session = None) -> int:
        return session.scalar(select(func.count()).select_from(State))

    @begin_session
    def get_screenshots_count(self, session: Session = None) -> int:
        return session.scalar(select(func.count()).select_from(Screenshot))

    @begin_session
    def get_total_filesize(self, session: Session = None) -> int:
        """Get the total filesize of all roms in the database, in bytes."""
        return session.scalar(select(func.sum(Rom.file_size_bytes)).select_from(Rom))
