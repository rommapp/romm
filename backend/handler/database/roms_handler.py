import functools
from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import (
    Integer,
    Row,
    String,
    Text,
    and_,
    case,
    cast,
    delete,
    false,
    func,
    literal,
    not_,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.orm import Query, Session, joinedload, noload, selectinload
from sqlalchemy.sql.elements import KeyedColumnElement

from config import ROMM_DB_DRIVER
from decorators.database import begin_session
from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from models.assets import Save, Screenshot, State
from models.platform import Platform
from models.rom import Rom, RomFile, RomMetadata, RomNote, RomUser
from utils.database import json_array_contains_value

from .base_handler import DBBaseHandler

EJS_SUPPORTED_PLATFORMS = [
    UPS._3DO,
    UPS.AMIGA,
    UPS.AMIGA_CD,
    UPS.AMIGA_CD32,
    UPS.ARCADE,
    UPS.NEOGEOAES,
    UPS.NEOGEOMVS,
    UPS.ATARI2600,
    UPS.ATARI5200,
    UPS.ATARI7800,
    UPS.C_PLUS_4,
    UPS.C64,
    UPS.CPET,
    UPS.C64,
    UPS.C128,
    UPS.COLECOVISION,
    UPS.JAGUAR,
    UPS.LYNX,
    UPS.NEO_GEO_POCKET,
    UPS.NEO_GEO_POCKET_COLOR,
    UPS.NES,
    UPS.FAMICOM,
    UPS.FDS,
    UPS.N64,
    UPS.N64DD,
    UPS.NDS,
    UPS.NINTENDO_DSI,
    UPS.GB,
    UPS.GBA,
    UPS.PC_FX,
    UPS.PHILIPS_CD_I,
    UPS.PSX,
    UPS.PSP,
    UPS.SEGACD,
    UPS.GENESIS,
    UPS.SMS,
    UPS.GAMEGEAR,
    UPS.SATURN,
    UPS.SNES,
    UPS.SFAM,
    UPS.TG16,
    UPS.VIC_20,
    UPS.VIRTUALBOY,
    UPS.WONDERSWAN,
    UPS.WONDERSWAN_COLOR,
]

STRIP_ARTICLES_REGEX = r"^(the|a|an)\s+"


def _create_metadata_id_case(
    prefix: str, id_column: KeyedColumnElement, platform_id_column: KeyedColumnElement
):
    return case(
        (
            id_column.isnot(None),
            func.concat(
                f"{prefix}-",
                platform_id_column,
                "-",
                id_column,
            ),
        ),
        else_=None,
    )


def with_details(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        kwargs["query"] = select(Rom).options(
            # Ensure platform is loaded for main ROM objects
            joinedload(Rom.platform),
            selectinload(Rom.saves).options(
                noload(Save.rom),
                noload(Save.user),
            ),
            selectinload(Rom.states).options(
                noload(State.rom),
                noload(State.user),
            ),
            selectinload(Rom.screenshots).options(
                noload(Screenshot.rom),
            ),
            selectinload(Rom.rom_users).options(noload(RomUser.rom)),
            selectinload(Rom.metadatum).options(noload(RomMetadata.rom)),
            selectinload(Rom.files).options(noload(RomFile.rom)),
            selectinload(Rom.sibling_roms).options(
                noload(Rom.platform), noload(Rom.metadatum)
            ),
            selectinload(Rom.collections),
        )
        return func(*args, **kwargs)

    return wrapper


def with_simple(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        kwargs["query"] = select(Rom).options(
            # Ensure platform is loaded for main ROM objects
            joinedload(Rom.platform),
            # Display properties for the current user (last_played)
            selectinload(Rom.rom_users).options(noload(RomUser.rom)),
            # Sort table by metadata (first_release_date)
            selectinload(Rom.metadatum).options(noload(RomMetadata.rom)),
            # Required for multi-file ROM actions and 3DS QR code
            selectinload(Rom.files).options(noload(RomFile.rom)),
            # Show sibling rom badges on cards
            selectinload(Rom.sibling_roms).options(
                noload(Rom.platform), noload(Rom.metadatum)
            ),
        )
        return func(*args, **kwargs)

    return wrapper


class DBRomsHandler(DBBaseHandler):
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
    @with_details
    def get_roms_by_ids(
        self, ids: list[int], *, query: Query = None, session: Session = None
    ) -> Sequence[Rom]:
        """Get multiple ROMs by their IDs."""
        if not ids:
            return []
        return session.scalars(query.filter(Rom.id.in_(ids))).all()

    def filter_by_platform_id(self, query: Query, platform_id: int):
        return query.filter(Rom.platform_id == platform_id)

    def filter_by_collection_id(
        self, query: Query, session: Session, collection_id: int
    ):
        from . import db_collection_handler

        collection = db_collection_handler.get_collection(collection_id)

        if collection:
            return query.filter(Rom.id.in_(collection.rom_ids))
        return query

    def filter_by_virtual_collection_id(
        self, query: Query, session: Session, virtual_collection_id: str
    ):
        from . import db_collection_handler

        v_collection = db_collection_handler.get_virtual_collection(
            virtual_collection_id
        )

        if v_collection:
            return query.filter(Rom.id.in_(v_collection.rom_ids))
        return query

    def filter_by_smart_collection_id(
        self, query: Query, session: Session, smart_collection_id: int, user_id: int
    ):
        from . import db_collection_handler

        smart_collection = db_collection_handler.get_smart_collection(
            smart_collection_id
        )

        if smart_collection:
            # Ensure the latest ROMs are loaded
            smart_collection = smart_collection.update_properties(user_id)
            return query.filter(Rom.id.in_(smart_collection.rom_ids))
        return query

    def filter_by_search_term(self, query: Query, search_term: str):
        return query.filter(
            or_(
                Rom.fs_name.ilike(f"%{search_term}%"),
                Rom.name.ilike(f"%{search_term}%"),
            )
        )

    def filter_by_matched(self, query: Query, value: bool) -> Query:
        """Filter based on whether the rom is matched to a metadata provider."""
        predicate = or_(
            Rom.igdb_id.isnot(None),
            Rom.moby_id.isnot(None),
            Rom.ss_id.isnot(None),
            Rom.ra_id.isnot(None),
            Rom.launchbox_id.isnot(None),
            Rom.hasheous_id.isnot(None),
            Rom.tgdb_id.isnot(None),
            Rom.flashpoint_id.isnot(None),
        )
        if not value:
            predicate = not_(predicate)
        return query.filter(predicate)

    def filter_by_favorite(
        self, query: Query, session: Session, value: bool, user_id: int | None
    ) -> Query:
        """Filter based on whether the rom is in the user's favorites collection."""
        if not user_id:
            return query

        from . import db_collection_handler

        favorites_collection = db_collection_handler.get_favorite_collection(user_id)
        if favorites_collection:
            predicate = Rom.id.in_(favorites_collection.rom_ids)
            if not value:
                predicate = not_(predicate)
            return query.filter(predicate)

        # If no favorites collection exists, return the original query if non-favorites
        # were requested, or an empty query if favorites were requested.
        if not value:
            return query
        return query.filter(false())

    def filter_by_duplicate(self, query: Query, value: bool) -> Query:
        """Filter based on whether the rom has duplicates."""
        predicate = Rom.sibling_roms.any()
        if not value:
            predicate = not_(predicate)
        return query.filter(predicate)

    def filter_by_playable(self, query: Query, value: bool) -> Query:
        """Filter based on whether the rom is playable on supported platforms."""
        predicate = Platform.slug.in_(EJS_SUPPORTED_PLATFORMS)
        if not value:
            predicate = not_(predicate)
        return query.join(Platform).filter(predicate)

    def filter_by_has_ra(self, query: Query, value: bool) -> Query:
        predicate = Rom.ra_id.isnot(None)
        if not value:
            predicate = not_(predicate)
        return query.filter(predicate)

    def filter_by_missing_from_fs(self, query: Query, value: bool) -> Query:
        predicate = Rom.missing_from_fs.isnot(False)
        if not value:
            predicate = not_(predicate)
        return query.filter(predicate)

    def filter_by_verified(self, query: Query):
        keys_to_check = [
            "tosec_match",
            "mame_arcade_match",
            "mame_mess_match",
            "nointro_match",
            "redump_match",
            "whdload_match",
            "ra_match",
            "fbneo_match",
            "puredos_match",
        ]

        if ROMM_DB_DRIVER == "postgresql":
            conditions = " OR ".join(
                f"(hasheous_metadata->>'{key}')::boolean" for key in keys_to_check
            )
            return query.filter(text(conditions))
        else:
            return query.filter(
                or_(*(Rom.hasheous_metadata[key].as_boolean() for key in keys_to_check))
            )

    def filter_by_genre(self, query: Query, session: Session, value: str) -> Query:
        return query.filter(
            json_array_contains_value(RomMetadata.genres, value, session=session)
        )

    def filter_by_franchise(self, query: Query, session: Session, value: str) -> Query:
        return query.filter(
            json_array_contains_value(RomMetadata.franchises, value, session=session)
        )

    def filter_by_collection(self, query: Query, session: Session, value: str) -> Query:
        return query.filter(
            json_array_contains_value(RomMetadata.collections, value, session=session)
        )

    def filter_by_company(self, query: Query, session: Session, value: str) -> Query:
        return query.filter(
            json_array_contains_value(RomMetadata.companies, value, session=session)
        )

    def filter_by_age_rating(self, query: Query, session: Session, value: str) -> Query:
        return query.filter(
            json_array_contains_value(RomMetadata.age_ratings, value, session=session)
        )

    def filter_by_status(self, query: Query, selected_status: str):
        status_filter = RomUser.status == selected_status
        if selected_status == "now_playing":
            status_filter = RomUser.now_playing.is_(True)
        elif selected_status == "backlogged":
            status_filter = RomUser.backlogged.is_(True)
        elif selected_status == "hidden":
            status_filter = RomUser.hidden.is_(True)

        if selected_status == "hidden":
            return query.filter(status_filter)

        return query.filter(status_filter, RomUser.hidden.is_(False))

    def filter_by_region(self, query: Query, session: Session, value: str) -> Query:
        return query.filter(
            json_array_contains_value(Rom.regions, value, session=session)
        )

    def filter_by_language(self, query: Query, session: Session, value: str) -> Query:
        return query.filter(
            json_array_contains_value(Rom.languages, value, session=session)
        )

    @begin_session
    def filter_roms(
        self,
        query: Query,
        platform_id: int | None = None,
        collection_id: int | None = None,
        virtual_collection_id: str | None = None,
        smart_collection_id: int | None = None,
        search_term: str | None = None,
        matched: bool | None = None,
        favorite: bool | None = None,
        duplicate: bool | None = None,
        playable: bool | None = None,
        has_ra: bool | None = None,
        missing: bool | None = None,
        verified: bool | None = None,
        group_by_meta_id: bool = False,
        selected_genre: str | None = None,
        selected_franchise: str | None = None,
        selected_collection: str | None = None,
        selected_company: str | None = None,
        selected_age_rating: str | None = None,
        selected_status: str | None = None,
        selected_region: str | None = None,
        selected_language: str | None = None,
        user_id: int | None = None,
        session: Session = None,
    ) -> Query[Rom]:
        from handler.scan_handler import MetadataSource

        if platform_id:
            query = self.filter_by_platform_id(query, platform_id)

        if collection_id:
            query = self.filter_by_collection_id(query, session, collection_id)

        if virtual_collection_id:
            query = self.filter_by_virtual_collection_id(
                query, session, virtual_collection_id
            )

        if smart_collection_id and user_id:
            query = self.filter_by_smart_collection_id(
                query, session, smart_collection_id, user_id
            )

        if search_term:
            query = self.filter_by_search_term(query, search_term)

        if matched is not None:
            query = self.filter_by_matched(query, value=matched)

        if favorite is not None:
            query = self.filter_by_favorite(
                query, session=session, value=favorite, user_id=user_id
            )

        if duplicate is not None:
            query = self.filter_by_duplicate(query, value=duplicate)

        if playable is not None:
            query = self.filter_by_playable(query, value=playable)

        if has_ra is not None:
            query = self.filter_by_has_ra(query, value=has_ra)

        if missing is not None:
            query = self.filter_by_missing_from_fs(query, value=missing)

        # TODO: Correctly support true/false values.
        if verified:
            query = self.filter_by_verified(query)

        # BEWARE YE WHO ENTERS HERE 💀
        if group_by_meta_id:
            # Convert NULL is_main_sibling to 0 (false) so it sorts after true values
            is_main_sibling_order = (
                func.coalesce(cast(RomUser.is_main_sibling, Integer), 0).desc()
                if user_id
                else literal(1)
            )

            # Create a subquery that identifies the primary ROM in each group
            # Priority order: is_main_sibling (desc), then by fs_name_no_ext (asc)
            base_subquery = query.subquery()
            group_subquery = (
                select(base_subquery.c.id)
                .select_from(base_subquery)
                .with_only_columns(
                    base_subquery.c.id,
                    base_subquery.c.fs_name_no_ext,
                    base_subquery.c.platform_id,
                    base_subquery.c.igdb_id,
                    base_subquery.c.ss_id,
                    base_subquery.c.moby_id,
                    base_subquery.c.ra_id,
                    base_subquery.c.hasheous_id,
                    base_subquery.c.launchbox_id,
                    base_subquery.c.tgdb_id,
                    base_subquery.c.flashpoint_id,
                )
                .outerjoin(
                    RomUser,
                    and_(
                        base_subquery.c.id == RomUser.rom_id, RomUser.user_id == user_id
                    ),
                )
                .add_columns(
                    func.row_number()
                    .over(
                        partition_by=func.coalesce(
                            _create_metadata_id_case(
                                MetadataSource.IGDB,
                                base_subquery.c.igdb_id,
                                base_subquery.c.platform_id,
                            ),
                            _create_metadata_id_case(
                                MetadataSource.SS,
                                base_subquery.c.ss_id,
                                base_subquery.c.platform_id,
                            ),
                            _create_metadata_id_case(
                                MetadataSource.MOBY,
                                base_subquery.c.moby_id,
                                base_subquery.c.platform_id,
                            ),
                            _create_metadata_id_case(
                                MetadataSource.RA,
                                base_subquery.c.ra_id,
                                base_subquery.c.platform_id,
                            ),
                            _create_metadata_id_case(
                                MetadataSource.HASHEOUS,
                                base_subquery.c.hasheous_id,
                                base_subquery.c.platform_id,
                            ),
                            _create_metadata_id_case(
                                MetadataSource.LAUNCHBOX,
                                base_subquery.c.launchbox_id,
                                base_subquery.c.platform_id,
                            ),
                            _create_metadata_id_case(
                                MetadataSource.TGDB,
                                base_subquery.c.tgdb_id,
                                base_subquery.c.platform_id,
                            ),
                            _create_metadata_id_case(
                                MetadataSource.FLASHPOINT,
                                base_subquery.c.flashpoint_id,
                                base_subquery.c.platform_id,
                            ),
                            _create_metadata_id_case(
                                "romm",
                                base_subquery.c.id,
                                base_subquery.c.platform_id,
                            ),
                        ),
                        order_by=[
                            is_main_sibling_order,
                            base_subquery.c.fs_name_no_ext.asc(),
                        ],
                    )
                    .label("row_num"),
                )
                .subquery()
            )

            # Add a filter to the original query to only include the primary ROM from each group
            query = query.filter(
                Rom.id.in_(
                    session.query(group_subquery.c.id).filter(
                        group_subquery.c.row_num == 1
                    )
                )
            )

        if (
            selected_genre
            or selected_franchise
            or selected_collection
            or selected_company
            or selected_age_rating
        ):
            query = query.outerjoin(RomMetadata)

        if selected_genre:
            query = self.filter_by_genre(query, session=session, value=selected_genre)
        if selected_franchise:
            query = self.filter_by_franchise(
                query, session=session, value=selected_franchise
            )
        if selected_collection:
            query = self.filter_by_collection(
                query, session=session, value=selected_collection
            )
        if selected_company:
            query = self.filter_by_company(
                query, session=session, value=selected_company
            )
        if selected_age_rating:
            query = self.filter_by_age_rating(
                query, session=session, value=selected_age_rating
            )
        if selected_region:
            query = self.filter_by_region(query, session=session, value=selected_region)
        if selected_language:
            query = self.filter_by_language(
                query, session=session, value=selected_language
            )

        # The RomUser table is already joined if user_id is set
        if selected_status and user_id:
            query = self.filter_by_status(query, selected_status)
        elif user_id:
            query = query.filter(
                or_(RomUser.hidden.is_(False), RomUser.hidden.is_(None))
            )

        return query

    @with_simple
    @begin_session
    def get_roms_query(
        self,
        *,
        order_by: str = "name",
        order_dir: str = "asc",
        user_id: int | None = None,
        query: Query = None,
        session: Session = None,
    ) -> tuple[Query[Rom], Any]:
        if user_id:
            query = query.outerjoin(
                RomUser, and_(RomUser.rom_id == Rom.id, RomUser.user_id == user_id)
            )

        if user_id and hasattr(RomUser, order_by) and not hasattr(Rom, order_by):
            order_attr = getattr(RomUser, order_by)
            query = query.filter(RomUser.user_id == user_id, order_attr.isnot(None))
        elif hasattr(RomMetadata, order_by) and not hasattr(Rom, order_by):
            order_attr = getattr(RomMetadata, order_by)
            query = query.outerjoin(RomMetadata, RomMetadata.rom_id == Rom.id).filter(
                order_attr.isnot(None)
            )
        elif hasattr(Rom, order_by):
            order_attr = getattr(Rom, order_by)
        else:
            order_attr = Rom.name

        order_attr_column = order_attr

        # Ignore case when the order attribute is a number
        if isinstance(order_attr.type, (String, Text)):
            # Remove any leading articles
            order_attr = func.trim(
                func.lower(order_attr).regexp_replace(STRIP_ARTICLES_REGEX, "", "i")
            )

        if order_dir.lower() == "desc":
            order_attr = order_attr.desc()
        else:
            order_attr = order_attr.asc()

        return query.order_by(order_attr), order_attr_column

    @begin_session
    def get_roms_scalar(
        self,
        *,
        session: Session = None,
        **kwargs,
    ) -> Sequence[Rom]:
        query, _ = self.get_roms_query(
            order_by=kwargs.get("order_by", "name"),
            order_dir=kwargs.get("order_dir", "asc"),
            user_id=kwargs.get("user_id", None),
        )
        roms = self.filter_roms(
            query=query,
            platform_id=kwargs.get("platform_id", None),
            collection_id=kwargs.get("collection_id", None),
            virtual_collection_id=kwargs.get("virtual_collection_id", None),
            search_term=kwargs.get("search_term", None),
            matched=kwargs.get("matched", None),
            favorite=kwargs.get("favorite", None),
            duplicate=kwargs.get("duplicate", None),
            playable=kwargs.get("playable", None),
            has_ra=kwargs.get("has_ra", None),
            missing=kwargs.get("missing", None),
            verified=kwargs.get("verified", None),
            selected_genre=kwargs.get("selected_genre", None),
            selected_franchise=kwargs.get("selected_franchise", None),
            selected_collection=kwargs.get("selected_collection", None),
            selected_company=kwargs.get("selected_company", None),
            selected_age_rating=kwargs.get("selected_age_rating", None),
            selected_status=kwargs.get("selected_status", None),
            selected_region=kwargs.get("selected_region", None),
            selected_language=kwargs.get("selected_language", None),
            user_id=kwargs.get("user_id", None),
        )
        return session.scalars(roms).all()

    @begin_session
    def with_char_index(
        self, query: Query, order_by_attr: Any, session: Session = None
    ) -> list[Row[tuple[str, int]]]:
        if isinstance(order_by_attr.type, (String, Text)):
            # Remove any leading articles
            order_by_attr = func.trim(
                func.lower(order_by_attr).regexp_replace(STRIP_ARTICLES_REGEX, "", "i")
            )
        else:
            order_by_attr = func.trim(
                func.lower(Rom.name).regexp_replace(STRIP_ARTICLES_REGEX, "", "i")
            )

        # Get the row number and first letter for each item
        subquery = (
            query.with_only_columns(Rom.id, Rom.name)  # type: ignore
            .add_columns(  # type: ignore
                func.substring(
                    order_by_attr,
                    1,
                    1,
                ).label("letter"),
                func.row_number().over(order_by=order_by_attr).label("position"),
            )
            .subquery()
        )

        # Get the minimum position for each letter
        return (
            session.query(
                subquery.c.letter, func.min(subquery.c.position - 1).label("position")
            )
            .group_by(subquery.c.letter)
            .order_by(subquery.c.letter)
            .all()
        )

    @begin_session
    @with_details
    def get_roms_by_fs_name(
        self,
        platform_id: int,
        fs_names: Iterable[str],
        query: Query = None,
        session: Session = None,
    ) -> dict[str, Rom]:
        """Retrieve a dictionary of roms by their filesystem names."""
        roms = (
            session.scalars(
                query.filter(Rom.fs_name.in_(fs_names)).filter_by(
                    platform_id=platform_id
                )
            )
            .unique()
            .all()
        )
        return {rom.fs_name: rom for rom in roms}

    @begin_session
    def update_rom(self, id: int, data: dict, session: Session = None) -> Rom:
        session.execute(
            update(Rom)
            .where(Rom.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )
        return session.query(Rom).filter_by(id=id).one()

    @begin_session
    def delete_rom(self, id: int, session: Session = None) -> None:
        session.execute(
            delete(Rom)
            .where(Rom.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def mark_missing_roms(
        self, platform_id: int, fs_roms_to_keep: list[str], session: Session = None
    ) -> Sequence[Rom]:
        missing_roms = (
            session.scalars(
                select(Rom)
                .order_by(Rom.fs_name.asc())
                .where(
                    and_(
                        Rom.platform_id == platform_id,
                        Rom.fs_name.not_in(fs_roms_to_keep),
                    )
                )
            )
            .unique()
            .all()
        )
        session.execute(
            update(Rom)
            .where(
                and_(
                    Rom.platform_id == platform_id, Rom.fs_name.not_in(fs_roms_to_keep)
                )
            )
            .values(**{"missing_from_fs": True})
            .execution_options(synchronize_session="evaluate")
        )
        return missing_roms

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
    def get_rom_user_by_id(self, id: int, session: Session = None) -> RomUser | None:
        return session.scalar(select(RomUser).filter_by(id=id).limit(1))

    @begin_session
    def update_rom_user(
        self, id: int, data: dict, session: Session = None
    ) -> RomUser | None:
        session.execute(
            update(RomUser)
            .where(RomUser.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

        rom_user = self.get_rom_user_by_id(id)
        if not rom_user:
            return None

        if not data.get("is_main_sibling", False):
            return rom_user

        rom = self.get_rom(rom_user.rom_id)
        if not rom:
            return rom_user

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

        return session.query(RomUser).filter_by(id=id).one()

    @begin_session
    def add_rom_file(self, rom_file: RomFile, session: Session = None) -> RomFile:
        return session.merge(rom_file)

    @begin_session
    def get_rom_files(self, rom_id: int, session: Session = None) -> Sequence[RomFile]:
        return session.scalars(select(RomFile).filter_by(rom_id=rom_id)).all()

    @begin_session
    def get_rom_file_by_id(self, id: int, session: Session = None) -> RomFile | None:
        return session.scalar(select(RomFile).filter_by(id=id).limit(1))

    @begin_session
    def update_rom_file(self, id: int, data: dict, session: Session = None) -> RomFile:
        session.execute(
            update(RomFile)
            .where(RomFile.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

        return session.query(RomFile).filter_by(id=id).one()

    @begin_session
    def purge_rom_files(
        self, rom_id: int, session: Session = None
    ) -> Sequence[RomFile]:
        purged_rom_files = (
            session.scalars(select(RomFile).filter_by(rom_id=rom_id)).unique().all()
        )
        session.execute(
            delete(RomFile)
            .where(RomFile.rom_id == rom_id)
            .execution_options(synchronize_session="evaluate")
        )
        return purged_rom_files

    # Note management methods
    @begin_session
    def get_rom_notes(
        self,
        rom_id: int,
        user_id: int,
        public_only: bool = False,
        search: str = "",
        tags: list[str] | None = None,
        session: Session = None,
    ) -> Sequence[RomNote]:
        query = session.query(RomNote).filter(RomNote.rom_id == rom_id)

        if public_only:
            query = query.filter(RomNote.is_public)
        else:
            # Include user's own notes (private + public) and public notes from others
            query = query.filter(or_(RomNote.user_id == user_id, RomNote.is_public))

        if search:
            query = query.filter(
                or_(RomNote.title.contains(search), RomNote.content.contains(search))
            )

        if tags:
            for tag in tags:
                query = query.filter(
                    json_array_contains_value(RomNote.tags, tag, session=session)
                )

        return query.order_by(RomNote.updated_at.desc()).all()

    @begin_session
    def create_rom_note(
        self,
        rom_id: int,
        user_id: int,
        title: str,
        content: str = "",
        is_public: bool = False,
        tags: list[str] | None = None,
        session: Session = None,
    ) -> dict:
        note = RomNote(
            rom_id=rom_id,
            user_id=user_id,
            title=title,
            content=content,
            is_public=is_public,
            tags=tags or [],
        )
        session.add(note)
        session.flush()  # To get the ID

        # Return dict to avoid detached instance issues
        return {
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "is_public": note.is_public,
            "tags": note.tags,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
            "rom_id": note.rom_id,
            "user_id": note.user_id,
        }

    @begin_session
    def update_rom_note(
        self,
        note_id: int,
        user_id: int,
        session: Session = None,
        **fields,
    ) -> dict | None:
        note = (
            session.query(RomNote)
            .filter(RomNote.id == note_id, RomNote.user_id == user_id)
            .first()
        )

        if not note:
            return None

        for field, value in fields.items():
            if hasattr(note, field):
                setattr(note, field, value)

        session.flush()  # Ensure changes are committed

        # Return dict to avoid detached instance issues
        return {
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "is_public": note.is_public,
            "tags": note.tags,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
            "rom_id": note.rom_id,
            "user_id": note.user_id,
        }

    @begin_session
    def delete_rom_note(
        self, note_id: int, user_id: int, session: Session = None
    ) -> bool:
        result = session.execute(
            delete(RomNote).where(
                and_(RomNote.id == note_id, RomNote.user_id == user_id)
            )
        )
        return result.rowcount > 0

    @begin_session
    @with_details
    def get_rom_by_metadata_id(
        self,
        igdb: int | None = None,
        moby: int | None = None,
        ss: int | None = None,
        ra: int | None = None,
        launchbox: int | None = None,
        hasheous: int | None = None,
        tgdb: int | None = None,
        flashpoint: str | None = None,
        hltb: int | None = None,
        *,
        query: Query = None,
        session: Session = None,
    ) -> Rom | None:
        """Get a ROM by any metadata ID."""
        filters = []
        param_map = [
            (igdb, Rom.igdb_id),
            (moby, Rom.moby_id),
            (ss, Rom.ss_id),
            (ra, Rom.ra_id),
            (launchbox, Rom.launchbox_id),
            (hasheous, Rom.hasheous_id),
            (tgdb, Rom.tgdb_id),
            (flashpoint, Rom.flashpoint_id),
            (hltb, Rom.hltb_id),
        ]

        for value, column in param_map:
            if value is not None:
                filters.append(column == value)

        if not filters:
            return None

        # Use OR to find ROM matching any of the provided metadata IDs
        return session.scalar(query.filter(or_(*filters)).limit(1))
