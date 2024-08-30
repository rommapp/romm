from decorators.database import begin_session
from models.platform import Platform
from models.rom import Rom
from sqlalchemy import Select, delete, or_, select
from sqlalchemy.orm import Session

from .base_handler import DBBaseHandler


class DBPlatformsHandler(DBBaseHandler):
    @begin_session
    def add_platform(
        self,
        platform: Platform,
        session: Session,
    ) -> Platform:
        platform = session.merge(platform)
        session.flush()

        new_platform = session.scalar(
            select(Platform).filter_by(id=platform.id).limit(1)
        )
        if not new_platform:
            raise ValueError("Could not find newlyewly created platform")

        return new_platform

    @begin_session
    def get_platform(self, id: int, *, session: Session) -> Platform | None:
        return session.scalar(select(Platform).filter_by(id=id).limit(1))

    @begin_session
    def get_platforms(self, *, session: Session) -> Select[tuple[Platform]]:
        return (
            session.scalars(select(Platform).order_by(Platform.name.asc()))  # type: ignore[attr-defined]
            .unique()
            .all()
        )

    @begin_session
    def get_platform_by_fs_slug(
        self, fs_slug: str, session: Session
    ) -> Platform | None:
        return session.scalar(select(Platform).filter_by(fs_slug=fs_slug).limit(1))

    @begin_session
    def delete_platform(self, id: int, session: Session) -> None:
        # Remove all roms from that platforms first
        session.execute(
            delete(Rom)
            .where(Rom.platform_id == id)
            .execution_options(synchronize_session="evaluate")
        )

        session.execute(
            delete(Platform)
            .where(Platform.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def purge_platforms(self, fs_platforms: list[str], session: Session) -> int:
        return session.execute(
            delete(Platform)
            .where(or_(Platform.fs_slug.not_in(fs_platforms), Platform.slug.is_(None)))  # type: ignore[attr-defined]
            .execution_options(synchronize_session="fetch")
        )
