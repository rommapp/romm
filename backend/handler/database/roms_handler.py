import functools
from collections.abc import Iterable, Sequence
from datetime import datetime
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
from sqlalchemy.sql.selectable import Select

from config import ROMM_DB_DRIVER
from decorators.database import begin_session
from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from models.assets import Save, Screenshot, State
from models.platform import Platform
from models.rom import Rom, RomFile, RomMetadata, RomNote, RomUser
from utils.database import (
    json_array_contains_all,
    json_array_contains_any,
    json_array_contains_value,
)

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
            selectinload(Rom.platform),
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
            selectinload(Rom.files).options(
                joinedload(RomFile.rom).load_only(Rom.fs_path, Rom.fs_name)
            ),
            selectinload(Rom.sibling_roms).options(
                noload(Rom.platform), noload(Rom.metadatum)
            ),
            selectinload(Rom.collections),
            selectinload(Rom.notes),
        )
        return func(*args, **kwargs)

    return wrapper


def with_simple(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        kwargs["query"] = select(Rom).options(
            # Ensure platform is loaded for main ROM objects
            selectinload(Rom.platform),
            # Display properties for the current user (last_played)
            selectinload(Rom.rom_users).options(noload(RomUser.rom)),
            # Sort table by metadata (first_release_date)
            selectinload(Rom.metadatum).options(noload(RomMetadata.rom)),
            # Required for multi-file ROM actions and 3DS QR code
            selectinload(Rom.files).options(
                joinedload(RomFile.rom).load_only(Rom.fs_path, Rom.fs_name)
            ),
            # Show sibling rom badges on cards
            selectinload(Rom.sibling_roms).options(
                noload(Rom.platform), noload(Rom.metadatum)
            ),
            # Show notes indicator on cards
            selectinload(Rom.notes),
        )
        return func(*args, **kwargs)

    return wrapper


class DBRomsHandler(DBBaseHandler):
    @begin_session
    @with_details
    def add_rom(
        self,
        rom: Rom,
        query: Query = None,  # type: ignore
        session: Session = None,  # type: ignore
    ) -> Rom:
        rom = session.merge(rom)
        session.flush()

        return session.scalar(query.filter_by(id=rom.id).limit(1))

    @begin_session
    @with_details
    def get_rom(
        self,
        id: int,
        *,
        query: Query = None,  # type: ignore
        session: Session = None,  # type: ignore
    ) -> Rom | None:
        return session.scalar(query.filter_by(id=id).limit(1))

    @begin_session
    @with_details
    def get_roms_by_ids(
        self,
        ids: list[int],
        *,
        query: Query = None,  # type: ignore
        session: Session = None,  # type: ignore
    ) -> Sequence[Rom]:
        """Get multiple ROMs by their IDs."""
        if not ids:
            return []
        return session.scalars(query.filter(Rom.id.in_(ids))).all()

    def filter_by_platform_id(self, query: Query, platform_id: int):
        return query.filter(Rom.platform_id == platform_id)

    def _filter_by_platform_ids(
        self, query: Query, platform_ids: Sequence[int]
    ) -> Query:
        return query.filter(Rom.platform_id.in_(platform_ids))

    def _filter_by_collection_id(
        self, query: Query, session: Session, collection_id: int
    ):
        from . import db_collection_handler

        collection = db_collection_handler.get_collection(collection_id)

        if collection:
            return query.filter(Rom.id.in_(collection.rom_ids))
        return query

    def _filter_by_virtual_collection_id(
        self, query: Query, session: Session, virtual_collection_id: str
    ):
        from . import db_collection_handler

        v_collection = db_collection_handler.get_virtual_collection(
            virtual_collection_id
        )

        if v_collection:
            return query.filter(Rom.id.in_(v_collection.rom_ids))
        return query

    def _filter_by_smart_collection_id(
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

    def _filter_by_search_term(self, query: Query, search_term: str):
        return query.filter(
            or_(
                Rom.fs_name.ilike(f"%{search_term}%"),
                Rom.name.ilike(f"%{search_term}%"),
            )
        )

    def _filter_by_matched(self, query: Query, value: bool) -> Query:
        """Filter based on whether the rom is matched to a metadata provider.

        Args:
            value: True for matched ROMs, False for unmatched ROMs
        """
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

    def _filter_by_favorite(
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

    def _filter_by_duplicate(self, query: Query, value: bool) -> Query:
        """Filter based on whether the rom has duplicates."""
        predicate = Rom.sibling_roms.any()
        if not value:
            predicate = not_(predicate)
        return query.filter(predicate)

    def _filter_by_playable(self, query: Query, value: bool) -> Query:
        """Filter based on whether the rom is playable on supported platforms."""
        predicate = Platform.slug.in_(EJS_SUPPORTED_PLATFORMS)
        if not value:
            predicate = not_(predicate)
        return query.join(Platform).filter(predicate)

    def _filter_by_last_played(
        self, query: Query, value: bool, user_id: int | None = None
    ) -> Query:
        """Filter based on whether the rom has a last played value for the user."""
        if not user_id:
            return query

        has_last_played = (
            RomUser.last_played.is_(None)
            if not value
            else RomUser.last_played.isnot(None)
        )
        return query.filter(has_last_played)

    def _filter_by_has_ra(self, query: Query, value: bool) -> Query:
        predicate = Rom.ra_id.isnot(None)
        if not value:
            predicate = not_(predicate)
        return query.filter(predicate)

    def _filter_by_missing_from_fs(self, query: Query, value: bool) -> Query:
        predicate = Rom.missing_from_fs.isnot(False)
        if not value:
            predicate = not_(predicate)
        return query.filter(predicate)

    def _filter_by_verified(self, query: Query):
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

    def _filter_by_genres(
        self,
        query: Query,
        *,
        session: Session,
        values: Sequence[str],
        match_all: bool = False,
        match_none: bool = False,
    ) -> Query:
        op = json_array_contains_all if match_all else json_array_contains_any
        condition = op(RomMetadata.genres, values, session=session)
        return query.filter(~condition) if match_none else query.filter(condition)

    def _filter_by_franchises(
        self,
        query: Query,
        *,
        session: Session,
        values: Sequence[str],
        match_all: bool = False,
        match_none: bool = False,
    ) -> Query:
        op = json_array_contains_all if match_all else json_array_contains_any
        condition = op(RomMetadata.franchises, values, session=session)
        return query.filter(~condition) if match_none else query.filter(condition)

    def _filter_by_collections(
        self,
        query: Query,
        *,
        session: Session,
        values: Sequence[str],
        match_all: bool = False,
        match_none: bool = False,
    ) -> Query:
        op = json_array_contains_all if match_all else json_array_contains_any
        condition = op(RomMetadata.collections, values, session=session)
        return query.filter(~condition) if match_none else query.filter(condition)

    def _filter_by_companies(
        self,
        query: Query,
        *,
        session: Session,
        values: Sequence[str],
        match_all: bool = False,
        match_none: bool = False,
    ) -> Query:
        op = json_array_contains_all if match_all else json_array_contains_any
        condition = op(RomMetadata.companies, values, session=session)
        return query.filter(~condition) if match_none else query.filter(condition)

    def _filter_by_age_ratings(
        self,
        query: Query,
        *,
        session: Session,
        values: Sequence[str],
        match_all: bool = False,
        match_none: bool = False,
    ) -> Query:
        op = json_array_contains_all if match_all else json_array_contains_any
        condition = op(RomMetadata.age_ratings, values, session=session)
        return query.filter(~condition) if match_none else query.filter(condition)

    def _filter_by_status(self, query: Query, statuses: Sequence[str]):
        """Filter by one or more user statuses using OR logic."""
        if not statuses:
            return query

        status_filters = []
        for selected_status in statuses:
            if selected_status == "now_playing":
                status_filters.append(RomUser.now_playing.is_(True))
            elif selected_status == "backlogged":
                status_filters.append(RomUser.backlogged.is_(True))
            elif selected_status == "hidden":
                status_filters.append(RomUser.hidden.is_(True))
            else:
                status_filters.append(RomUser.status == selected_status)

        # If hidden is in the list, don't apply the hidden filter at the end
        if "hidden" in statuses:
            return query.filter(or_(*status_filters))

        return query.filter(or_(*status_filters), RomUser.hidden.is_(False))

    def _filter_by_regions(
        self,
        query: Query,
        *,
        session: Session,
        values: Sequence[str],
        match_all: bool = False,
        match_none: bool = False,
    ) -> Query:
        op = json_array_contains_all if match_all else json_array_contains_any
        condition = op(Rom.regions, values, session=session)
        return query.filter(~condition) if match_none else query.filter(condition)

    def _filter_by_languages(
        self,
        query: Query,
        *,
        session: Session,
        values: Sequence[str],
        match_all: bool = False,
        match_none: bool = False,
    ) -> Query:
        op = json_array_contains_all if match_all else json_array_contains_any
        condition = op(Rom.languages, values, session=session)
        return query.filter(~condition) if match_none else query.filter(condition)

    def _filter_by_player_counts(
        self,
        query: Query,
        *,
        session: Session,
        values: Sequence[str],
        match_all: bool = False,
        match_none: bool = False,
    ) -> Query:
        condition = RomMetadata.player_count.in_(values)
        if match_none:
            return query.filter(not_(condition))
        return query.filter(condition)

    @begin_session
    def filter_roms(
        self,
        query: Query,
        platform_ids: Sequence[int] | None = None,
        collection_id: int | None = None,
        virtual_collection_id: str | None = None,
        smart_collection_id: int | None = None,
        search_term: str | None = None,
        matched: bool | None = None,
        favorite: bool | None = None,
        duplicate: bool | None = None,
        last_played: bool | None = None,
        playable: bool | None = None,
        has_ra: bool | None = None,
        missing: bool | None = None,
        verified: bool | None = None,
        group_by_meta_id: bool = False,
        genres: Sequence[str] | None = None,
        franchises: Sequence[str] | None = None,
        collections: Sequence[str] | None = None,
        companies: Sequence[str] | None = None,
        age_ratings: Sequence[str] | None = None,
        statuses: Sequence[str] | None = None,
        regions: Sequence[str] | None = None,
        languages: Sequence[str] | None = None,
        player_counts: Sequence[str] | None = None,
        # Logic operators for multi-value filters
        genres_logic: str = "any",
        franchises_logic: str = "any",
        collections_logic: str = "any",
        companies_logic: str = "any",
        age_ratings_logic: str = "any",
        regions_logic: str = "any",
        languages_logic: str = "any",
        statuses_logic: str = "any",
        player_counts_logic: str = "any",
        user_id: int | None = None,
        updated_after: datetime | None = None,
        session: Session = None,  # type: ignore
    ) -> Query[Rom]:
        from handler.scan_handler import MetadataSource

        # Handle platform filtering - platform filtering always uses OR logic since ROMs belong to only one platform
        if platform_ids:
            query = self._filter_by_platform_ids(query, platform_ids)

        if collection_id:
            query = self._filter_by_collection_id(query, session, collection_id)

        if virtual_collection_id:
            query = self._filter_by_virtual_collection_id(
                query, session, virtual_collection_id
            )

        if smart_collection_id and user_id:
            query = self._filter_by_smart_collection_id(
                query, session, smart_collection_id, user_id
            )

        if search_term:
            query = self._filter_by_search_term(query, search_term)

        if matched is not None:
            query = self._filter_by_matched(query, value=matched)

        if favorite is not None:
            query = self._filter_by_favorite(
                query, session=session, value=favorite, user_id=user_id
            )

        if duplicate is not None:
            query = self._filter_by_duplicate(query, value=duplicate)

        if last_played is not None:
            query = self._filter_by_last_played(
                query, value=last_played, user_id=user_id
            )

        if playable is not None:
            query = self._filter_by_playable(query, value=playable)

        if has_ra is not None:
            query = self._filter_by_has_ra(query, value=has_ra)

        if missing is not None:
            query = self._filter_by_missing_from_fs(query, value=missing)

        # TODO: Correctly support true/false values.
        if verified:
            query = self._filter_by_verified(query)

        if updated_after:
            query = query.filter(Rom.updated_at > updated_after)

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

        # Optimize JOINs - only join tables when needed
        needs_metadata_join = any(
            [genres, franchises, collections, companies, age_ratings, player_counts]
        )

        if needs_metadata_join:
            query = query.outerjoin(RomMetadata)

        # Apply metadata and rom-level filters efficiently
        filters_to_apply = [
            (genres, genres_logic, self._filter_by_genres),
            (franchises, franchises_logic, self._filter_by_franchises),
            (collections, collections_logic, self._filter_by_collections),
            (companies, companies_logic, self._filter_by_companies),
            (age_ratings, age_ratings_logic, self._filter_by_age_ratings),
            (regions, regions_logic, self._filter_by_regions),
            (languages, languages_logic, self._filter_by_languages),
            (player_counts, player_counts_logic, self._filter_by_player_counts),
        ]

        for values, logic, filter_func in filters_to_apply:
            if values:
                query = filter_func(
                    query,
                    session=session,
                    values=values,
                    match_all=(logic == "all"),
                    match_none=(logic == "none"),
                )

        # The RomUser table is already joined if user_id is set
        if statuses and user_id:
            query = self._filter_by_status(query, statuses)
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
        query: Query = None,  # type: ignore
        session: Session = None,  # type: ignore
    ) -> tuple[Query[Rom], Any]:
        if user_id:
            query = query.outerjoin(
                RomUser, and_(RomUser.rom_id == Rom.id, RomUser.user_id == user_id)
            )

        if user_id and hasattr(RomUser, order_by) and not hasattr(Rom, order_by):
            order_attr = getattr(RomUser, order_by)
            query = query.filter(RomUser.user_id == user_id)
        elif hasattr(RomMetadata, order_by) and not hasattr(Rom, order_by):
            order_attr = getattr(RomMetadata, order_by)
            query = query.outerjoin(RomMetadata, RomMetadata.rom_id == Rom.id)
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
        session: Session = None,  # type: ignore
        **kwargs,
    ) -> Sequence[Rom]:
        query, _ = self.get_roms_query(
            order_by=kwargs.get("order_by", "name"),
            order_dir=kwargs.get("order_dir", "asc"),
            user_id=kwargs.get("user_id", None),
        )
        roms = self.filter_roms(
            query=query,
            platform_ids=kwargs.get("platform_ids", None),
            collection_id=kwargs.get("collection_id", None),
            virtual_collection_id=kwargs.get("virtual_collection_id", None),
            search_term=kwargs.get("search_term", None),
            matched=kwargs.get("matched", None),
            favorite=kwargs.get("favorite", None),
            duplicate=kwargs.get("duplicate", None),
            last_played=kwargs.get("last_played", None),
            playable=kwargs.get("playable", None),
            has_ra=kwargs.get("has_ra", None),
            missing=kwargs.get("missing", None),
            verified=kwargs.get("verified", None),
            genres=kwargs.get("genres", None),
            franchises=kwargs.get("franchises", None),
            collections=kwargs.get("collections", None),
            companies=kwargs.get("companies", None),
            age_ratings=kwargs.get("age_ratings", None),
            statuses=kwargs.get("statuses", None),
            regions=kwargs.get("regions", None),
            languages=kwargs.get("languages", None),
            player_counts=kwargs.get("player_counts", None),
            # Logic operators for multi-value filters
            genres_logic=kwargs.get("genres_logic", "any"),
            franchises_logic=kwargs.get("franchises_logic", "any"),
            collections_logic=kwargs.get("collections_logic", "any"),
            companies_logic=kwargs.get("companies_logic", "any"),
            age_ratings_logic=kwargs.get("age_ratings_logic", "any"),
            regions_logic=kwargs.get("regions_logic", "any"),
            languages_logic=kwargs.get("languages_logic", "any"),
            statuses_logic=kwargs.get("statuses_logic", "any"),
            player_counts_logic=kwargs.get("player_counts_logic", "any"),
            user_id=kwargs.get("user_id", None),
        )
        return session.scalars(roms).all()

    @begin_session
    def with_char_index(
        self,
        query: Query,
        order_by_attr: Any,
        session: Session = None,  # type: ignore
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
        query: Query = None,  # type: ignore
        session: Session = None,  # type: ignore
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
    def update_rom(
        self,
        id: int,
        data: dict,
        session: Session = None,  # type: ignore
    ) -> Rom:
        session.execute(
            update(Rom)
            .where(Rom.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )
        return session.query(Rom).filter_by(id=id).one()

    @begin_session
    def delete_rom(
        self,
        id: int,
        session: Session = None,  # type: ignore
    ) -> None:
        session.execute(
            delete(Rom)
            .where(Rom.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def mark_missing_roms(
        self,
        platform_id: int,
        fs_roms_to_keep: list[str],
        session: Session = None,  # type: ignore
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
        self,
        rom_id: int,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> RomUser:
        return session.merge(RomUser(rom_id=rom_id, user_id=user_id))

    @begin_session
    def get_rom_user(
        self,
        rom_id: int,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> RomUser | None:
        return session.scalar(
            select(RomUser).filter_by(rom_id=rom_id, user_id=user_id).limit(1)
        )

    @begin_session
    def get_rom_user_by_id(
        self,
        id: int,
        session: Session = None,  # type: ignore
    ) -> RomUser | None:
        return session.scalar(select(RomUser).filter_by(id=id).limit(1))

    @begin_session
    def update_rom_user(
        self,
        id: int,
        data: dict,
        session: Session = None,  # type: ignore
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
    def add_rom_file(
        self,
        rom_file: RomFile,
        session: Session = None,  # type: ignore
    ) -> RomFile:
        return session.merge(rom_file)

    @begin_session
    def get_rom_file_by_id(
        self,
        id: int,
        session: Session = None,  # type: ignore
    ) -> RomFile | None:
        return session.scalar(select(RomFile).filter_by(id=id).limit(1))

    @begin_session
    def update_rom_file(
        self,
        id: int,
        data: dict,
        session: Session = None,  # type: ignore
    ) -> RomFile:
        session.execute(
            update(RomFile)
            .where(RomFile.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

        return session.query(RomFile).filter_by(id=id).one()

    @begin_session
    def purge_rom_files(
        self,
        rom_id: int,
        session: Session = None,  # type: ignore
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
        session: Session = None,  # type: ignore
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
        session: Session = None,  # type: ignore
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
        session: Session = None,  # type: ignore
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
        self,
        note_id: int,
        user_id: int,
        session: Session = None,  # type: ignore
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
        igdb_id: int | None = None,
        moby_id: int | None = None,
        ss_id: int | None = None,
        ra_id: int | None = None,
        launchbox_id: int | None = None,
        hasheous_id: int | None = None,
        tgdb_id: int | None = None,
        flashpoint_id: str | None = None,
        hltb_id: int | None = None,
        *,
        query: Query = None,  # type: ignore
        session: Session = None,  # type: ignore
    ) -> Rom | None:
        """
        Get a ROM by any metadata ID.

        Returns the first ROM that matches any of the provided metadata IDs.
        """
        # Build filters for non-nil IDs
        filters = [
            column == value
            for value, column in [
                (igdb_id, Rom.igdb_id),
                (moby_id, Rom.moby_id),
                (ss_id, Rom.ss_id),
                (ra_id, Rom.ra_id),
                (launchbox_id, Rom.launchbox_id),
                (hasheous_id, Rom.hasheous_id),
                (tgdb_id, Rom.tgdb_id),
                (flashpoint_id, Rom.flashpoint_id),
                (hltb_id, Rom.hltb_id),
            ]
            if value is not None
        ]

        if not filters:
            return None

        # Return the first ROM matching any of the provided metadata IDs
        return session.scalar(query.filter(or_(*filters)).limit(1))

    @begin_session
    @with_details
    def get_rom_by_hash(
        self,
        crc_hash: str | None,
        md5_hash: str | None,
        sha1_hash: str | None,
        *,
        query: Query = None,  # type: ignore
        session: Session = None,  # type: ignore
    ) -> Rom | None:
        """
        Get a ROM by calculated hash value.

        Returns the first ROM that matches any of the provided hash values.
        """
        # Build filters for non-nil IDs
        filters = [
            column == value
            for value, column in [
                (crc_hash, Rom.crc_hash),
                (md5_hash, Rom.md5_hash),
                (sha1_hash, Rom.sha1_hash),
                (crc_hash, RomFile.crc_hash),
                (md5_hash, RomFile.md5_hash),
                (sha1_hash, RomFile.sha1_hash),
            ]
            if value is not None
        ]

        if not filters:
            return None

        # Return the first ROM matching any of the provided hash values
        return session.scalar(query.outerjoin(Rom.files).filter(or_(*filters)).limit(1))

    def _collect_filter_values(
        self,
        session: Session,
        statement: Select,
    ) -> dict:
        genres = set()
        franchises = set()
        collections = set()
        companies = set()
        game_modes = set()
        age_ratings = set()
        player_counts = set()
        regions = set()
        languages = set()
        platforms = set()

        for row in session.execute(statement):
            g, f, cl, co, gm, ar, pc, rg, lg, pid = row
            if g:
                genres.update(g)
            if f:
                franchises.update(f)
            if cl:
                collections.update(cl)
            if co:
                companies.update(co)
            if gm:
                game_modes.update(gm)
            if ar:
                age_ratings.update(ar)
            if pc:
                player_counts.add(pc)
            if rg:
                regions.update(rg)
            if lg:
                languages.update(lg)
            platforms.add(pid)

        return {
            "genres": sorted(genres),
            "franchises": sorted(franchises),
            "collections": sorted(collections),
            "companies": sorted(companies),
            "game_modes": sorted(game_modes),
            "age_ratings": sorted(age_ratings),
            "player_counts": sorted(player_counts),
            "regions": sorted(regions),
            "languages": sorted(languages),
            "platforms": sorted(platforms),
        }

    @begin_session
    def with_filter_values(
        self,
        query: Query,
        session: Session = None,  # type: ignore
    ) -> dict:
        """
        Returns the list of filters given the current subset of ROMs in the query
        """
        ids_subq = query.with_only_columns(Rom.id).scalar_subquery()  # type: ignore

        statement = (
            select(
                RomMetadata.genres,
                RomMetadata.franchises,
                RomMetadata.collections,
                RomMetadata.companies,
                RomMetadata.game_modes,
                RomMetadata.age_ratings,
                RomMetadata.player_count,
                Rom.regions,
                Rom.languages,
                Rom.platform_id,
            )
            .select_from(Rom)
            .join(RomMetadata, Rom.id == RomMetadata.rom_id)
            .where(Rom.id.in_(ids_subq))
        )

        return self._collect_filter_values(session, statement)

    @begin_session
    def get_rom_filters(
        self,
        session: Session = None,  # type: ignore
    ) -> dict:
        """
        Returns all filter values across all ROM metadata
        """
        statement = select(
            RomMetadata.genres,
            RomMetadata.franchises,
            RomMetadata.collections,
            RomMetadata.companies,
            RomMetadata.game_modes,
            RomMetadata.age_ratings,
            RomMetadata.player_count,
            Rom.regions,
            Rom.languages,
            Rom.platform_id,
        )

        return self._collect_filter_values(session, statement)
