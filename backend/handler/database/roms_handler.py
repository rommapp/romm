import functools

from decorators.database import begin_session
from models.rom import Rom, UserRomProps
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.orm import Query, Session, aliased, contains_eager, selectinload

from .base_handler import DBBaseHandler


class ImplementationError(Exception): ...


def with_assets(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        session = kwargs.get("session")
        if session is None:
            raise ImplementationError(
                f"Method {func} bad implementation: kwarg 'session' is required"
            )

        user_id = kwargs.get("user_id")
        if user_id is None:
            raise ImplementationError(
                f"Method {func} bad implementation: kwarg 'user_id' is required"
            )

        try:
            rom_set = select(Rom).filter_by(id=kwargs["id"])
        except KeyError:
            rom_set = select(Rom)

        # Subquery to filter user_rom_props by user_id
        subquery = (
            select(aliased(Rom.user_rom_props)).filter_by(user_id=user_id).subquery()
        )

        # Construct the query to join Rom with the filtered user_rom_props
        kwargs["query"] = rom_set.outerjoin(subquery, Rom.user_rom_props).options(
            selectinload(Rom.saves),
            selectinload(Rom.states),
            selectinload(Rom.screenshots),
            contains_eager(Rom.user_rom_props, alias=subquery),
        )
        return func(*args, **kwargs)

    return wrapper


class DBRomsHandler(DBBaseHandler):
    def _filter(self, data, platform_id: int | None, search_term: str):
        if platform_id:
            data = data.filter(Rom.platform_id == platform_id)

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
    @with_assets
    def add_rom(self, rom: Rom, query: Query = None, session: Session = None) -> Rom:
        rom = session.merge(rom)
        session.flush()
        return session.scalar(query.filter_by(id=rom.id).limit(1))

    @begin_session
    @with_assets
    def get_rom(
        self,
        *,
        id: int | None = None,
        user_id: int | None = None,
        query: Query = None,
        session: Session = None,
    ) -> Rom | None:
        return session.scalar(query.limit(1))

    @begin_session
    @with_assets
    def get_roms(
        self,
        *,
        platform_id: int | None = None,
        user_id: int | None = None,
        search_term: str = "",
        order_by: str = "name",
        order_dir: str = "asc",
        limit: int = None,
        query: Query = None,
        session: Session = None,
    ) -> tuple[Rom | None]:
        return (
            session.scalars(
                self._order(
                    self._filter(query, platform_id, search_term),
                    order_by,
                    order_dir,
                ).limit(limit)
            )
            .unique()
            .all()
        )

    @begin_session
    @with_assets
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
    @with_assets
    def get_rom_by_filename_no_tags(
        self, file_name_no_tags: str, query: Query = None, session: Session = None
    ) -> Rom | None:
        return session.scalar(
            query.filter_by(file_name_no_tags=file_name_no_tags).limit(1)
        )

    @begin_session
    @with_assets
    def get_rom_by_filename_no_ext(
        self, file_name_no_ext: str, query: Query = None, session: Session = None
    ) -> Rom | None:
        return session.scalar(
            query.filter_by(file_name_no_ext=file_name_no_ext).limit(1)
        )

    @begin_session
    def get_rom_siblings(self, rom: Rom, session: Session = None):
        return session.scalars(
            select(Rom).where(
                and_(
                    Rom.platform_id == rom.platform_id,
                    Rom.id != rom.id,
                    or_(
                        and_(
                            Rom.igdb_id == rom.igdb_id,
                            Rom.igdb_id.isnot(None),
                            Rom.igdb_id != "",
                        ),
                        and_(
                            Rom.moby_id == rom.moby_id,
                            Rom.moby_id.isnot(None),
                            Rom.moby_id != "",
                        ),
                    ),
                )
            )
        ).all()

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
        self, platform_id: int, roms: list[str], session: Session = None
    ) -> int:
        return session.execute(
            delete(Rom)
            .where(and_(Rom.platform_id == platform_id, Rom.file_name.not_in(roms)))  # type: ignore[attr-defined]
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def add_rom_props(
        self, rom_id: int, user_id: int, session: Session = None
    ) -> UserRomProps:
        return session.merge(UserRomProps(rom_id=rom_id, user_id=user_id))

    @begin_session
    def get_rom_props(
        self, rom_id: int, user_id: int, session: Session = None
    ) -> UserRomProps | None:
        return session.scalar(
            select(UserRomProps).filter_by(rom_id=rom_id, user_id=user_id).limit(1)
        )

    @begin_session
    def update_rom_props(
        self, id: int, data: dict, rom: Rom, user_id: int, session: Session = None
    ) -> UserRomProps:
        session.execute(
            update(UserRomProps)
            .where(UserRomProps.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )
        if data["is_main_sibling"]:
            siblings = [rom.id for rom in rom.get_sibling_roms()]
            session.execute(
                update(UserRomProps)
                .where(
                    and_(
                        UserRomProps.rom_id.in_(siblings),
                        UserRomProps.user_id == user_id,
                    )
                )
                .values(is_main_sibling=False)
            )
        return self.get_rom_props(rom.id, user_id)
