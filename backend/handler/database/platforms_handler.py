import functools

from decorators.database import begin_session
from models.platform import Platform
from models.rom import Rom
from sqlalchemy import Select, delete, or_, select
from sqlalchemy.orm import Query, Session, selectinload

from .base_handler import DBBaseHandler


def with_roms(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        session = kwargs.get("session")
        if session is None:
            raise ValueError("session is required")

        kwargs["query"] = select(Platform).options(
            selectinload(Platform.roms).load_only(Rom.id)
        )
        return func(*args, **kwargs)

    return wrapper


class DBPlatformsHandler(DBBaseHandler):
    @begin_session
    @with_roms
    def add_platform(
        self, platform: Platform, query: Query = None, session: Session = None
    ) -> Platform | None:
        platform = session.merge(platform)
        session.flush()

        return session.scalar(query.filter_by(id=platform.id).limit(1))

    @begin_session
    @with_roms
    def get_platform(
        self, id: int, *, query: Query = None, session: Session = None
    ) -> Platform | None:
        return session.scalar(query.filter_by(id=id).limit(1))

    @begin_session
    def get_platforms(self, *, session: Session = None) -> Select[tuple[Platform]]:
        return (
            session.scalars(select(Platform).order_by(Platform.name.asc()))  # type: ignore[attr-defined]
            .unique()
            .all()
        )

    @begin_session
    @with_roms
    def get_platform_by_fs_slug(
        self, fs_slug: str, query: Query = None, session: Session = None
    ) -> Platform | None:
        return session.scalar(query.filter_by(fs_slug=fs_slug).limit(1))

    @begin_session
    def delete_platform(self, id: int, session: Session = None) -> int:
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
    def purge_platforms(self, fs_platforms: list[str], session: Session = None) -> int:
        return session.execute(
            delete(Platform)
            .where(or_(Platform.fs_slug.not_in(fs_platforms), Platform.slug.is_(None)))  # type: ignore[attr-defined]
            .execution_options(synchronize_session="fetch")
        )
