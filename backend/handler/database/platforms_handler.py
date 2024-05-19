import functools
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, Query, joinedload

from decorators.database import begin_session
from models.platform import Platform
from models.rom import Rom

from .base_handler import DBBaseHandler


def with_query(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        session = kwargs.get("session")
        if session is None:
            raise ValueError("session is required")

        kwargs["query"] = session.query(Platform).options(
            joinedload(Platform.roms)
        )
        return func(*args, **kwargs)

    return wrapper


class DBPlatformsHandler(DBBaseHandler):
    @begin_session
    @with_query
    def add_platform(
        self, platform: Platform, query: Query = None, session: Session = None
    ) -> Platform | None:
        session.merge(platform)
        session.flush()

        return query.filter(Platform.id == platform.id).first()

    @begin_session
    @with_query
    def get_platforms(
        self, id: int = None, query: Query = None, session: Session = None
    ) -> list[Platform] | Platform | None:
        return (
            query.get(Platform, id)
            if id
            else (
                session.scalars(query.order_by(Platform.name.asc()))
                .unique()
                .all()
            )
        )

    @begin_session
    @with_query
    def get_platform_by_fs_slug(
        self, fs_slug: str, query: Query = None, session: Session = None
    ) -> Platform | None:
        return session.scalars(
            query.filter_by(fs_slug=fs_slug).limit(1)
        ).first()

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
    def purge_platforms(
        self, fs_platforms: list[str], session: Session = None
    ) -> int:
        return session.execute(
            delete(Platform)
            .where(or_(Platform.fs_slug.not_in(fs_platforms), Platform.slug.is_(None)))
            .where(
                select(func.count())
                .select_from(Rom)
                .filter_by(platform_id=Platform.id)
                .as_scalar()
                == 0
            )
            .execution_options(synchronize_session="fetch")
        )
