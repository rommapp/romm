from decorators.database import begin_session
from models.assets import Save, Screenshot, State
from models.platform import Platform
from models.rom import Rom, RomFile
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from .base_handler import DBBaseHandler


class DBStatsHandler(DBBaseHandler):
    @begin_session
    def get_platforms_count(self, session: Session = None) -> int:
        """Get the number of platforms with any roms."""
        return (
            session.scalar(
                select(func.count(distinct(Rom.platform_id))).select_from(Rom)
            )
            or 0
        )

    @begin_session
    def get_roms_count(self, session: Session = None) -> int:
        return session.scalar(select(func.count()).select_from(Rom)) or 0

    @begin_session
    def get_saves_count(self, session: Session = None) -> int:
        return session.scalar(select(func.count()).select_from(Save)) or 0

    @begin_session
    def get_states_count(self, session: Session = None) -> int:
        return session.scalar(select(func.count()).select_from(State)) or 0

    @begin_session
    def get_screenshots_count(self, session: Session = None) -> int:
        return session.scalar(select(func.count()).select_from(Screenshot)) or 0

    @begin_session
    def get_total_filesize(self, session: Session = None) -> int:
        """Get the total filesize of all roms in the database, in bytes."""
        return (
            session.scalar(
                select(func.sum(RomFile.file_size_bytes)).select_from(RomFile)
            )
            or 0
        )

    @begin_session
    def get_platform_filesize(self, platform_id: int, session: Session = None) -> int:
        """Get the total filesize of all roms in the database, in bytes."""
        return (
            session.scalar(
                select(func.sum(RomFile.file_size_bytes))
                .select_from(RomFile)
                .join(Rom)
                .filter(Rom.platform_id == platform_id)
            )
            or 0
        )

    @begin_session
    def get_platforms_filesize(self, session: Session = None) -> list[dict]:
        """
        Returns a list of dicts: each with 'id', 'name', and 'filesize' for each platform.
        """
        platform_rows = (
            session.execute(
                select(Platform.id, Platform.name)
                .join(Rom, Rom.platform_id == Platform.id)
                .group_by(Platform.id, Platform.name)
            )
        ).all()
        return [
            {
                "id": platform_id,
                "name": platform_name,
                "filesize": self.get_platform_filesize(platform_id, session=session),
            }
            for platform_id, platform_name in platform_rows
        ]
