from decorators.database import begin_session
from models.platform import Platform
from models.rom import Rom
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from .base_handler import DBBaseHandler


class DBPlatformsHandler(DBBaseHandler):
    @begin_session
    def add_platform(self, platform: Platform, session: Session = None) -> Platform:
        return session.merge(platform)

    @begin_session
    def get_platforms(
        self, id: int | None = None, session: Session = None
    ) -> Platform | list[Platform] | None:
        return (
            session.get(Platform, id)
            if id
            else (
                session.scalars(select(Platform).order_by(Platform.name.asc()))  # type: ignore[attr-defined]
                .unique()
                .all()
            )
        )

    @begin_session
    def get_platform_by_fs_slug(
        self, fs_slug: str, session: Session = None
    ) -> Platform | None:
        return session.scalars(
            select(Platform).filter_by(fs_slug=fs_slug).limit(1)
        ).first()

    @begin_session
    def delete_platform(self, id: int, session: Session = None) -> None:
        # Remove all roms from that platforms first
        session.execute(
            delete(Rom)
            .where(Rom.platform_id == id)
            .execution_options(synchronize_session="evaluate")
        )
        return session.execute(
            delete(Platform)
            .where(Platform.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def get_rom_count(self, platform_id: int, session: Session = None) -> int:
        return session.scalar(
            select(func.count()).select_from(Rom).filter_by(platform_id=platform_id)
        )

    @begin_session
    def purge_platforms(self, fs_platforms: list[str], session: Session = None) -> None:
        return session.execute(
            delete(Platform)
            .where(or_(Platform.fs_slug.not_in(fs_platforms), Platform.slug.is_(None)))  # type: ignore[attr-defined]
            .execution_options(synchronize_session="fetch")
        )
