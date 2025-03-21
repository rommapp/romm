from typing import Sequence

from decorators.database import begin_session
from models.platform import Platform
from models.rom import Rom
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from .base_handler import DBBaseHandler


class DBPlatformsHandler(DBBaseHandler):
    @begin_session
    def add_platform(
        self,
        platform: Platform,
        session: Session = None,
    ) -> Platform:
        platform = session.merge(platform)
        session.flush()

        return session.query(Platform).filter_by(id=platform.id).one()

    @begin_session
    def get_platform(self, id: int, *, session: Session = None) -> Platform | None:
        return session.scalar(select(Platform).filter_by(id=id).limit(1))

    @begin_session
    def get_platforms(self, *, session: Session = None) -> Sequence[Platform]:
        return (
            session.scalars(select(Platform).order_by(Platform.name.asc()))
            .unique()
            .all()
        )

    @begin_session
    def get_platform_by_fs_slug(
        self, fs_slug: str, session: Session = None
    ) -> Platform | None:
        return session.scalar(select(Platform).filter_by(fs_slug=fs_slug).limit(1))

    @begin_session
    def delete_platform(self, id: int, session: Session = None) -> None:
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
    def purge_platforms(
        self, fs_platforms_to_keep: list[str], session: Session = None
    ) -> Sequence[Platform]:
        purged_platforms = (
            session.scalars(
                select(Platform)
                .order_by(Platform.name.asc())
                .where(
                    or_(
                        Platform.fs_slug.not_in(fs_platforms_to_keep),
                        Platform.slug.is_(None),
                    )
                )
            )  # type: ignore[attr-defined]
            .unique()
            .all()
        )
        session.execute(
            delete(Platform)
            .where(or_(Platform.fs_slug.not_in(fs_platforms_to_keep), Platform.slug.is_(None)))  # type: ignore[attr-defined]
            .execution_options(synchronize_session="fetch")
        )
        return purged_platforms
