import functools
from collections.abc import Callable, Collection, Sequence
from datetime import datetime
from typing import Any, cast

from sqlalchemy import Select, delete, func, or_, select, update
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.sql.elements import ColumnElement

from decorators.database import INJECTED_SESSION, begin_session
from handler.auth.rom_visibility import UNRESTRICTED, RomVisibilityFilter
from models.platform import Platform
from models.rom import Rom

from .base_handler import DBBaseHandler

# Default for a `query` parameter that with_firmware fills before the body runs.
INJECTED_PLATFORM_QUERY = cast(Select[Platform], None)


def with_firmware[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        kwargs["query"] = select(Platform).options(
            selectinload(Platform.firmware),
        )
        return func(*args, **kwargs)

    return wrapper


def _with_visible_totals(
    session: Session, query: Select[Platform], visibility: RomVisibilityFilter
) -> list[Platform]:
    """Load `query`'s platforms, their totals counting only the ROMs `visibility` shows."""
    hidden: list[ColumnElement[bool]] = []
    if visibility.hidden_rom_ids:
        # Matched by primary key, so a few hides cost a few lookups.
        hidden.append(Rom.id.in_(visibility.hidden_rom_ids))
    row_hidden = visibility.row_hidden_clause()
    if visibility.has_age_rule and row_hidden is not None:
        hidden.append(row_hidden)
    if not hidden:
        return list(session.scalars(query).unique().all())

    totals = (
        select(
            Rom.platform_id,
            func.count(Rom.id).label("rom_count"),
            func.coalesce(func.sum(Rom.fs_size_bytes), 0).label("fs_size_bytes"),
        )
        .where(or_(*hidden))
        .group_by(Rom.platform_id)
        .subquery()
    )
    # One statement, so the hidden totals never exceed the full totals it computes.
    rows = (
        session.execute(
            query.add_columns(totals.c.rom_count, totals.c.fs_size_bytes).outerjoin(
                totals, totals.c.platform_id == Platform.id
            )
        )
        .unique()
        .all()
    )
    platforms = []
    for platform, hidden_count, hidden_size in rows:
        if hidden_count:
            set_committed_value(
                platform, "rom_count", platform.rom_count - hidden_count
            )
            set_committed_value(
                platform, "fs_size_bytes", platform.fs_size_bytes - int(hidden_size)
            )
        platforms.append(platform)
    return platforms


class DBPlatformsHandler(DBBaseHandler):
    @begin_session
    @with_firmware
    def add_platform(
        self,
        platform: Platform,
        query: Select[Platform] = INJECTED_PLATFORM_QUERY,
        session: Session = INJECTED_SESSION,
    ) -> Platform:
        platform = session.merge(platform)
        session.flush()

        return session.scalars(query.filter_by(id=platform.id).limit(1)).one()

    @begin_session
    def update_platform(
        self,
        id: int,
        data: dict[str, Any],
        session: Session = INJECTED_SESSION,
    ) -> Platform:
        session.execute(
            update(Platform)
            .where(Platform.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )
        return session.scalars(select(Platform).filter_by(id=id)).one()

    @begin_session
    @with_firmware
    def get_platform(
        self,
        id: int,
        visibility: RomVisibilityFilter = UNRESTRICTED,
        query: Select[Platform] = INJECTED_PLATFORM_QUERY,
        session: Session = INJECTED_SESSION,
    ) -> Platform | None:
        """The platform, its totals counting only the ROMs `visibility` shows."""
        platforms = _with_visible_totals(
            session, query.filter_by(id=id).limit(1), visibility
        )
        return platforms[0] if platforms else None

    @begin_session
    @with_firmware
    def get_platforms(
        self,
        updated_after: datetime | None = None,
        hidden_platform_ids: Collection[int] | None = None,
        visibility: RomVisibilityFilter = UNRESTRICTED,
        query: Select[Platform] = INJECTED_PLATFORM_QUERY,
        session: Session = INJECTED_SESSION,
    ) -> Sequence[Platform]:
        if updated_after:
            query = query.filter(Platform.updated_at > updated_after)

        # Admin-driven visibility (opt-out): exclude platforms hidden from the
        # caller. Empty/None (e.g. admins) skips filtering.
        if hidden_platform_ids:
            query = query.filter(Platform.id.not_in(hidden_platform_ids))

        return _with_visible_totals(
            session, query.order_by(Platform.name.asc()), visibility
        )

    @begin_session
    def get_platform_ids(
        self,
        hidden_platform_ids: Collection[int] | None = None,
        session: Session = INJECTED_SESSION,
    ) -> list[int]:
        """Ids only, deliberately off `with_firmware`: its eager load fires anyway."""
        query = select(Platform).order_by(Platform.name.asc())

        if hidden_platform_ids:
            query = query.filter(Platform.id.not_in(hidden_platform_ids))

        return list(session.scalars(query.with_only_columns(Platform.id)).all())

    @begin_session
    @with_firmware
    def get_platform_by_fs_slug(
        self,
        fs_slug: str,
        query: Select[Platform] = INJECTED_PLATFORM_QUERY,
        session: Session = INJECTED_SESSION,
    ) -> Platform | None:
        platform = session.scalar(query.filter_by(fs_slug=fs_slug).limit(1))
        if platform:
            return platform

        # Folder names are matched case-insensitively everywhere else, so a
        # folder renamed only in case is the same platform, not a new one.
        return session.scalar(
            query.filter(func.lower(Platform.fs_slug) == fs_slug.lower()).limit(1)
        )

    @begin_session
    @with_firmware
    def get_platform_by_slug(
        self,
        slug: str,
        query: Select[Platform] = INJECTED_PLATFORM_QUERY,
        session: Session = INJECTED_SESSION,
    ) -> Platform | None:
        return session.scalar(query.filter_by(slug=slug).limit(1))

    @begin_session
    def delete_platform(
        self,
        id: int,
        session: Session = INJECTED_SESSION,
    ) -> None:
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
    def mark_missing_platforms(
        self,
        fs_platforms_to_keep: list[str],
        session: Session = INJECTED_SESSION,
    ) -> Sequence[Platform]:
        missing_platforms = (
            session.scalars(
                select(Platform)
                .order_by(Platform.name.asc())
                .where(
                    or_(
                        Platform.fs_slug.not_in(fs_platforms_to_keep),
                        Platform.slug.is_(None),
                    )
                )
            )
            .unique()
            .all()
        )
        session.execute(
            update(Platform)
            .where(
                or_(
                    Platform.fs_slug.not_in(fs_platforms_to_keep),
                    Platform.slug.is_(None),
                )
            )
            .values(**{"missing_from_fs": True})
            .execution_options(synchronize_session="fetch")
        )

        session.execute(
            update(Rom)
            .where(Rom.platform_id.in_([p.id for p in missing_platforms]))
            .values(**{"missing_from_fs": True})
            .execution_options(synchronize_session="fetch")
        )
        return missing_platforms
