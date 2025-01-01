import functools
from collections.abc import Iterable

from decorators.database import begin_session
from models.collection import Collection
from models.rom import Rom, RomUser
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.orm import Query, Session, selectinload
from utils.database import json_array_contains_value

from .base_handler import DBBaseHandler


def with_details(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        session = kwargs.get("session")
        if session is None:
            raise TypeError(
                f"{func} is missing required kwarg 'session' with type 'Session'"
            )

        kwargs["query"] = select(Rom).options(
            selectinload(Rom.saves),
            selectinload(Rom.states),
            selectinload(Rom.screenshots),
            selectinload(Rom.rom_users),
            selectinload(Rom.sibling_roms),
        )
        return func(*args, **kwargs)

    return wrapper


def with_simple(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        session = kwargs.get("session")
        if session is None:
            raise TypeError(
                f"{func} is missing required kwarg 'session' with type 'Session'"
            )

        kwargs["query"] = select(Rom).options(
            selectinload(Rom.rom_users), selectinload(Rom.sibling_roms)
        )
        return func(*args, **kwargs)

    return wrapper


class DBRomsHandler(DBBaseHandler):
    def _filter(
        self,
        data,
        platform_id: int | None,
        collection_id: int | None,
        search_term: str,
        session: Session,
    ):
        if platform_id:
            data = data.filter(Rom.platform_id == platform_id)

        if collection_id:
            collection = (
                session.query(Collection)
                .filter(Collection.id == collection_id)
                .one_or_none()
            )
            if collection:
                data = data.filter(Rom.id.in_(collection.roms))

        if search_term:
            data = data.filter(
                or_(
                    Rom.file_name.ilike(f"%{search_term}%"),  # type: ignore[attr-defined]
                    Rom.name.ilike(f"%{search_term}%"),  # type: ignore[attr-defined]
                )
            )

        return data

    def _order(self, data, order_by: str, order_dir: str):
        if order_by == "id":
            _column = Rom.id
        else:
            _column = func.lower(Rom.name)

        if order_dir == "desc":
            return data.order_by(_column.desc())
        else:
            return data.order_by(_column.asc())

    @begin_session
    @with_details
    def add_rom(self, rom: Rom, query: Query = None, session: Session = None) -> Rom:
        rom = session.merge(rom)
        session.flush()

        return session.scalar(query.filter_by(id=rom.id).limit(1))

    @begin_session
    @with_details
    def get_rom(
        self, id: int, *, query: Query = None, session: Session = None
    ) -> Rom | None:
        return session.scalar(query.filter_by(id=id).limit(1))

    @begin_session
    @with_simple
    def get_roms(
        self,
        *,
        platform_id: int | None = None,
        collection_id: int | None = None,
        search_term: str = "",
        order_by: str = "name",
        order_dir: str = "asc",
        limit: int | None = None,
        offset: int | None = None,
        query: Query = None,
        session: Session = None,
    ) -> list[Rom]:
        filtered_query = self._filter(
            query, platform_id, collection_id, search_term, session
        )
        ordered_query = self._order(filtered_query, order_by, order_dir)
        offset_query = ordered_query.offset(offset)
        limited_query = offset_query.limit(limit)
        return session.scalars(limited_query).unique().all()

    @begin_session
    @with_details
    def get_rom_by_filename(
        self,
        platform_id: int,
        file_name: str,
        query: Query = None,
        session: Session = None,
    ) -> Rom | None:
        return session.scalar(
            query.filter_by(platform_id=platform_id, file_name=file_name).limit(1)
        )

    @begin_session
    def get_roms_by_filename(
        self,
        platform_id: int,
        file_names: Iterable[str],
        query: Query = None,
        session: Session = None,
    ) -> dict[str, Rom]:
        """Retrieve a dictionary of roms by their file names."""
        query = query or select(Rom)
        roms = (
            session.scalars(
                query.filter(Rom.file_name.in_(file_names)).filter_by(
                    platform_id=platform_id
                )
            )
            .unique()
            .all()
        )
        return {rom.file_name: rom for rom in roms}

    @begin_session
    @with_details
    def get_rom_by_filename_no_tags(
        self, file_name_no_tags: str, query: Query = None, session: Session = None
    ) -> Rom | None:
        return session.scalar(
            query.filter_by(file_name_no_tags=file_name_no_tags).limit(1)
        )

    @begin_session
    @with_details
    def get_rom_by_filename_no_ext(
        self, file_name_no_ext: str, query: Query = None, session: Session = None
    ) -> Rom | None:
        return session.scalar(
            query.filter_by(file_name_no_ext=file_name_no_ext).limit(1)
        )

    @begin_session
    def get_rom_collections(
        self, rom: Rom, session: Session = None
    ) -> list[Collection]:
        return (
            session.scalars(
                select(Collection)
                .filter(
                    json_array_contains_value(
                        Collection.roms, str(rom.id), session=session
                    )
                )
                .order_by(Collection.name.asc())
            )
            .unique()
            .all()
        )

    @begin_session
    def update_rom(self, id: int, data: dict, session: Session = None) -> Rom:
        return session.execute(
            update(Rom)
            .where(Rom.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def delete_rom(self, id: int, session: Session = None) -> Rom:
        return session.execute(
            delete(Rom)
            .where(Rom.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def purge_roms(
        self, platform_id: int, fs_roms: list[str], session: Session = None
    ) -> list[Rom]:
        purged_roms = (
            session.scalars(
                select(Rom)
                .order_by(Rom.file_name.asc())
                .where(
                    and_(Rom.platform_id == platform_id, Rom.file_name.not_in(fs_roms))
                )
            )  # type: ignore[attr-defined]
            .unique()
            .all()
        )
        session.execute(
            delete(Rom)
            .where(and_(Rom.platform_id == platform_id, Rom.file_name.not_in(fs_roms)))  # type: ignore[attr-defined]
            .execution_options(synchronize_session="evaluate")
        )
        return purged_roms

    @begin_session
    def add_rom_user(
        self, rom_id: int, user_id: int, session: Session = None
    ) -> RomUser:
        return session.merge(RomUser(rom_id=rom_id, user_id=user_id))

    @begin_session
    def get_rom_user(
        self, rom_id: int, user_id: int, session: Session = None
    ) -> RomUser | None:
        return session.scalar(
            select(RomUser).filter_by(rom_id=rom_id, user_id=user_id).limit(1)
        )

    @begin_session
    @with_simple
    def get_roms_user(
        self,
        *,
        user_id: int,
        platform_id: int | None = None,
        collection_id: int | None = None,
        search_term: str = "",
        order_by: str = "name",
        order_dir: str = "asc",
        limit: int | None = None,
        offset: int | None = None,
        query: Query = None,
        session: Session = None,
    ) -> list[Rom]:
        filtered_query = (
            query.join(RomUser)
            .filter(RomUser.user_id == user_id)
            .order_by(RomUser.last_played.desc())
        )
        filtered_query = self._filter(
            filtered_query, platform_id, collection_id, search_term, session
        )
        offset_query = filtered_query.offset(offset)
        limited_query = offset_query.limit(limit)
        return session.scalars(limited_query).unique().all()

    @begin_session
    def get_rom_user_by_id(self, id: int, session: Session = None) -> RomUser | None:
        return session.scalar(select(RomUser).filter_by(id=id).limit(1))

    @begin_session
    def update_rom_user(self, id: int, data: dict, session: Session = None) -> RomUser:
        session.execute(
            update(RomUser)
            .where(RomUser.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

        rom_user = self.get_rom_user_by_id(id)

        if data.get("is_main_sibling", False):
            rom = self.get_rom(rom_user.rom_id)

            session.execute(
                update(RomUser)
                .where(
                    and_(
                        RomUser.rom_id.in_(r.id for r in rom.sibling_roms),
                        RomUser.user_id == rom_user.user_id,
                    )
                )
                .values(is_main_sibling=False)
            )

        return self.get_rom_user_by_id(id)
