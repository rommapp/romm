import functools
import json
import re
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

from redis.exceptions import WatchError
from sqlalchemy import (
    Integer,
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
from sqlalchemy.orm import (
    Query,
    QueryableAttribute,
    Session,
    joinedload,
    load_only,
    noload,
    selectinload,
    undefer,
)
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import Select

from config import ROMM_DB_DRIVER
from decorators.database import begin_session
from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from handler.redis_handler import sync_cache
from models.assets import Save, Screenshot, State
from models.base import compute_file_name_parts
from models.platform import Platform
from models.rom import (
    Rom,
    RomFile,
    RomFileCategory,
    RomMetadata,
    RomNote,
    RomUser,
    SiblingRom,
    compute_name_sort_key,
)
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
    UPS.CPET,
    UPS.C64,
    UPS.C128,
    UPS.COLECOVISION,
    UPS.JAGUAR,
    UPS.LYNX,
    UPS.DOS,
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
    UPS.GBC,
    UPS.PC_FX,
    UPS.PHILIPS_CD_I,
    UPS.PSX,
    UPS.PSP,
    UPS.SEGACD,
    UPS.SEGA32,
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

RUFFLE_SUPPORTED_PLATFORMS = [
    UPS.BROWSER,
]

# Used to remove native full-text SQL operators
FULLTEXT_BOOLEAN_OPERATORS_REGEX = re.compile(r'[+\-~<>()"@*]')

# 3 is the default minimum size in InnoDB
FULLTEXT_MIN_TOKEN_SIZE = 3

# Cached ROM filter values (genres/franchises/etc.) so it doesn't get
# recomputed on every call to /api/roms
ROM_FILTERS_CACHE_VERSION_KEY = "filter_values:ver"
ROM_FILTERS_CACHE_KEYS_PREFIX = "filter_values:keys"
ROM_FILTERS_CACHE_TTL = 60 * 60 * 24 * 7  # 7 days


def _cache_value_to_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


def _filter_values_cache_version() -> str:
    return _cache_value_to_str(sync_cache.get(ROM_FILTERS_CACHE_VERSION_KEY)) or "0"


def _filter_values_cache_keys_key(version: str) -> str:
    return f"{ROM_FILTERS_CACHE_KEYS_PREFIX}:v{version}"


def _store_versioned_cache(redis_key: str, version: str, result: Any) -> None:
    version_keys_set = _filter_values_cache_keys_key(version)
    with sync_cache.pipeline() as pipe:
        try:
            pipe.watch(ROM_FILTERS_CACHE_VERSION_KEY)
            current_version = (
                _cache_value_to_str(pipe.get(ROM_FILTERS_CACHE_VERSION_KEY)) or "0"
            )
            if current_version != version:
                pipe.unwatch()
            else:
                pipe.multi()
                pipe.set(redis_key, json.dumps(result), ex=ROM_FILTERS_CACHE_TTL)
                pipe.sadd(version_keys_set, redis_key)
                pipe.expire(version_keys_set, ROM_FILTERS_CACHE_TTL)
                pipe.execute()
        except WatchError:
            pass


def _create_metadata_id_case(
    prefix: str,
    id_column: ColumnElement,
    platform_id_column: ColumnElement,
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
            # Multi-file downloads, 3DS QR codes, and metadata matching
            selectinload(Rom.files).options(
                joinedload(RomFile.rom).load_only(Rom.fs_path, Rom.fs_name)
            ),
            selectinload(Rom.sibling_roms).options(
                noload(Rom.platform),
                noload(Rom.metadatum),
                # Per-sibling is_main_sibling resolution for the
                # SiblingRomSchema needs each sibling's RomUser for the
                # request user — the relationship is `lazy="raise"`, so
                # it has to be eager-loaded here.
                selectinload(Rom.rom_users).options(noload(RomUser.rom)),
                load_only(
                    Rom.id,
                    Rom.name,
                    Rom.fs_name_no_tags,
                    Rom.fs_name_no_ext,
                ),
            ),
            selectinload(Rom.collections),
            selectinload(Rom.notes),
            undefer(Rom.multi_file),
            undefer(Rom.top_level_file_count),
            undefer(Rom.has_manual_files),
            undefer(Rom.has_soundtrack),
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

    def get_files_for_roms(
        self,
        rom_ids: list[int],
        *,
        session: Session,
    ) -> dict[int, list[RomFile]]:
        """Return {rom_id: [RomFile, ...]} for the given rom IDs in a single query.

        Used by the list endpoint to serialize files without relying on the
        query's relationship eager-load surviving pagination.
        """
        if not rom_ids:
            return {}

        files = session.scalars(
            select(RomFile).where(RomFile.rom_id.in_(rom_ids))
        ).all()

        buckets: dict[int, list[RomFile]] = {rom_id: [] for rom_id in rom_ids}
        for file in files:
            buckets[file.rom_id].append(file)

        return buckets

    def get_siblings_for_roms(
        self,
        rom_ids: list[int],
        user_id: int,
        *,
        session: Session,
    ) -> dict[int, list[tuple[Rom, bool]]]:
        """Return {rom_id: [(sibling Rom, is_main_sibling), ...]} in a single query.

        Joins sibling_roms → roms (only the columns SiblingRomSchema needs) and
        left-joins rom_user for the requesting user, so the per-user
        `is_main_sibling` flag is resolved without hydrating the wide roms table
        or its JSON metadata on every page.
        """
        if not rom_ids:
            return {}

        rows = session.execute(
            select(
                SiblingRom.rom_id,
                Rom,
                func.coalesce(RomUser.is_main_sibling, false()).label(
                    "is_main_sibling"
                ),
            )
            .join(Rom, Rom.id == SiblingRom.sibling_rom_id)
            .outerjoin(
                RomUser,
                and_(
                    RomUser.rom_id == SiblingRom.sibling_rom_id,
                    RomUser.user_id == user_id,
                ),
            )
            .where(SiblingRom.rom_id.in_(rom_ids))
            .options(
                load_only(
                    Rom.name,
                    Rom.fs_name_no_tags,
                    Rom.fs_name_no_ext,
                )
            )
        ).all()

        # Dedupe by (parent rom, sibling id) so a duplicate join row doesn't
        # surface the same sibling twice on the wire.
        seen: dict[int, set[int]] = {rom_id: set() for rom_id in rom_ids}
        buckets: dict[int, list[tuple[Rom, bool]]] = {rom_id: [] for rom_id in rom_ids}
        for rom_id, sibling, is_main in rows:
            if sibling.id in seen[rom_id]:
                continue
            seen[rom_id].add(sibling.id)
            buckets[rom_id].append((sibling, bool(is_main)))

        return buckets

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

    def _build_fulltext_boolean_query(self, term: str) -> str | None:
        words = FULLTEXT_BOOLEAN_OPERATORS_REGEX.sub(" ", term).split()
        if not words or any(len(word) < FULLTEXT_MIN_TOKEN_SIZE for word in words):
            return None
        return " ".join(f"+{word}*" for word in words)

    def _build_fulltext_relevance(self, search_term: str) -> str | None:
        parts: list[str] = []
        for term in search_term.split("|"):
            words = FULLTEXT_BOOLEAN_OPERATORS_REGEX.sub(" ", term).split()
            if len(words) > 1:
                parts.append('"' + " ".join(words) + '"')
        return " ".join(parts) if parts else None

    def _filter_by_search_term(self, query: Query, search_term: str):
        terms = [term.strip() for term in search_term.split("|")]
        terms = [term for term in terms if term]
        if not terms:
            return query

        if ROMM_DB_DRIVER in ("mariadb", "mysql"):
            match_clauses: list[Any] = []
            for idx, term in enumerate(terms):
                boolean_query = self._build_fulltext_boolean_query(term)
                if boolean_query is None:
                    match_clauses = []
                    break
                param = f"fulltext_search_{idx}"
                match_clauses.append(
                    text(
                        f"MATCH(roms.name, roms.fs_name) "
                        f"AGAINST(:{param} IN BOOLEAN MODE)"
                    ).bindparams(**{param: boolean_query})
                )
            if match_clauses:
                return query.filter(or_(*match_clauses))

        # psql and full-text fallback
        term_conditions = []
        for term in terms:
            word_conditions = [
                or_(Rom.fs_name.ilike(f"%{word}%"), Rom.name.ilike(f"%{word}%"))
                for word in term.split()
            ]
            if word_conditions:
                term_conditions.append(and_(*word_conditions))
        return query.filter(or_(*term_conditions))

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
        predicate = or_(
            Platform.slug.in_(EJS_SUPPORTED_PLATFORMS),
            Platform.slug.in_(RUFFLE_SUPPORTED_PLATFORMS),
        )
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

    def _filter_by_verified(self, query: Query, value: bool) -> Query:
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
            predicate = text(f"({conditions})")
            if not value:
                predicate = text(f"NOT ({conditions})")
            return query.filter(predicate)
        else:
            predicate = or_(
                *(Rom.hasheous_metadata[key].as_boolean() for key in keys_to_check)
            )
            if not value:
                predicate = not_(predicate)
            return query.filter(predicate)

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

    def _filter_by_status(
        self,
        query: Query,
        *,
        session: Session,
        values: Sequence[str],
        match_all: bool = False,
        match_none: bool = False,
    ):
        if not values:
            return query

        status_filters = []
        for selected_status in values:
            if selected_status == "now_playing":
                status_filters.append(RomUser.now_playing.is_(True))
            elif selected_status == "backlogged":
                status_filters.append(RomUser.backlogged.is_(True))
            elif selected_status == "hidden":
                status_filters.append(RomUser.hidden.is_(True))
            else:
                status_filters.append(RomUser.status == selected_status)

        comb = and_ if match_all else or_
        condition = comb(*status_filters)

        # Apply negation if match_none, otherwise apply condition
        query = query.filter(~condition) if match_none else query.filter(condition)

        # Don't apply the hidden filter is hidden is set
        if "hidden" in values:
            return query

        return query.filter(or_(RomUser.hidden.is_(False), RomUser.hidden.is_(None)))

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
        include_file_stats: bool = False,
        include_files: bool = False,
        hidden_platform_ids: Sequence[int] | None = None,
        hidden_rom_ids: Sequence[int] | None = None,
        session: Session = None,  # type: ignore
    ) -> Query[Rom]:
        from handler.scan_handler import MetadataSource

        query = query.options(
            # Ensure platform is loaded for main ROM objects
            selectinload(Rom.platform),
            # Display properties for the current user (last_played)
            selectinload(Rom.rom_users).options(noload(RomUser.rom)),
            # Sort table by metadata (first_release_date)
            selectinload(Rom.metadatum).options(noload(RomMetadata.rom)),
            # Show sibling rom badges on cards
            selectinload(Rom.sibling_roms).options(
                noload(Rom.platform), noload(Rom.metadatum)
            ),
            # Notes indicator on cards
            selectinload(Rom.notes),
        )

        # Only load files (and the RomFile.rom backref needed by `is_top_level` /
        # `file_name_for_download`) when the caller iterates them — e.g. the
        # feed endpoints. The gallery/list and filter-value paths serialize
        # SimpleRomSchema without files, so they skip this entirely.
        if include_files:
            query = query.options(
                selectinload(Rom.files).options(
                    joinedload(RomFile.rom).load_only(Rom.fs_path, Rom.fs_name)
                )
            )

        # Correlated subqueries and only undefer when the caller serializes the
        # gallery-card flags. Feeds and filter-value lookups don't need them.
        if include_file_stats:
            query = query.options(
                undefer(Rom.multi_file),
                undefer(Rom.top_level_file_count),
                undefer(Rom.has_manual_files),
                undefer(Rom.has_soundtrack),
            )

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

        if verified is not None:
            query = self._filter_by_verified(query, value=verified)

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
            # Priority order: is_main_sibling (desc), then by fs_name_no_ext (asc).
            # Materialize only the columns the dedup window needs (not all of
            # Rom, whose JSON metadata blobs make the derived table huge), and
            # drop the carried-over ORDER BY the window doesn't use.
            base_subquery = (
                query.order_by(None)
                .with_only_columns(
                    Rom.id,
                    Rom.fs_name_no_ext,
                    Rom.platform_id,
                    Rom.igdb_id,
                    Rom.ss_id,
                    Rom.moby_id,
                    Rom.ra_id,
                    Rom.hasheous_id,
                    Rom.launchbox_id,
                    Rom.tgdb_id,
                    Rom.flashpoint_id,
                )
                .subquery()
            )
            # Only id and the row number flow downstream; the partition/order
            # inputs are read straight from base_subquery, so keeping them out of
            # this SELECT keeps the window's temp table narrow (carrying the wide
            # fs_name_no_ext through it spilled the sort to disk).
            group_subquery = (
                select(base_subquery.c.id)
                .select_from(base_subquery)
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
            query = self._filter_by_status(
                query,
                session=session,
                values=statuses,
                match_all=(statuses_logic == "all"),
                match_none=(statuses_logic == "none"),
            )
        elif user_id:
            query = query.filter(
                or_(RomUser.hidden.is_(False), RomUser.hidden.is_(None))
            )

        # Admin-driven visibility (opt-out): hide platforms/roms an admin has
        # hidden from this user/group. Orthogonal to the personal RomUser.hidden
        # toggle above. Empty sets (e.g. admins) skip filtering entirely.
        if hidden_platform_ids:
            query = query.filter(Rom.platform_id.not_in(hidden_platform_ids))
        if hidden_rom_ids:
            query = query.filter(Rom.id.not_in(hidden_rom_ids))

        return query

    @begin_session
    def get_roms_query(
        self,
        *,
        order_by: str = "",
        order_dir: str = "asc",
        search_term: str | None = None,
        user_id: int | None = None,
        session: Session = None,  # type: ignore
    ) -> tuple[Query[Rom], Any]:
        query = select(Rom)

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

        # Use indexed `name_sort_key` to have fast access to names without
        # articles (the, a, an) and leading digits. The key is derived from
        # `name` at write time, or holds a custom override when one is set.
        if order_attr is Rom.name:
            order_attr = Rom.name_sort_key

        order_attr_column = order_attr

        if order_dir.lower() == "desc":
            order_attr = order_attr.desc()
        else:
            order_attr = order_attr.asc()

        relevance_clause = None
        if search_term and ROMM_DB_DRIVER in ("mariadb", "mysql"):
            relevance = self._build_fulltext_relevance(search_term)
            if relevance:
                relevance_clause = text(
                    "MATCH(roms.name, roms.fs_name) "
                    "AGAINST(:relevance IN BOOLEAN MODE) DESC"
                ).bindparams(relevance=relevance)

        if order_by:  # explicit sort wins, relevance breaks ties
            order_clauses = [order_attr]
            if relevance_clause is not None:
                order_clauses.append(relevance_clause)
        else:  # no sort selected: relevance leads, name is the tiebreaker
            order_clauses = [order_attr]
            if relevance_clause is not None:
                order_clauses.insert(0, relevance_clause)

        return query.order_by(*order_clauses), order_attr_column  # type: ignore

    @begin_session
    def get_roms_scalar(
        self,
        *,
        only_fields: Sequence[QueryableAttribute] | None = None,
        session: Session = None,  # type: ignore
        **kwargs,
    ) -> Sequence[Rom]:
        query, _ = self.get_roms_query(
            order_by=kwargs.get("order_by", ""),
            order_dir=kwargs.get("order_dir", "asc"),
            search_term=kwargs.get("search_term", None),
            user_id=kwargs.get("user_id", None),
        )

        if only_fields:
            query = query.options(load_only(*only_fields))

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
            group_by_meta_id=kwargs.get("group_by_meta_id", False),
            include_files=kwargs.get("include_files", False),
            hidden_platform_ids=kwargs.get("hidden_platform_ids", None),
            hidden_rom_ids=kwargs.get("hidden_rom_ids", None),
        )
        return session.scalars(roms).all()

    @begin_session
    def with_char_index(
        self,
        query: Query,
        order_by_attr: Any,
        *,
        cache_key: str | None = None,
        order_dir: str = "asc",
        session: Session = None,  # type: ignore
    ) -> list[tuple[str, int]]:
        redis_key: str | None = None
        version: str | None = None
        if cache_key:
            version = _filter_values_cache_version()
            redis_key = f"char_index:{cache_key}:v{version}"
            cached = sync_cache.get(redis_key)
            if cached is not None:
                return json.loads(cached)

        # Drop any ordering carried over from the main query (e.g. search relevance).
        # This builds its own positional ordering below.
        query = query.order_by(None)

        if not isinstance(order_by_attr.type, (String, Text)):
            order_by_attr = Rom.name_sort_key

        # The alpha-strip only needs each first letter's starting offset, not a
        # positional number for every row. Counting rows per letter and
        # accumulating those counts avoids row_number() over the whole library,
        # which forced a full materialization + filesort on large libraries.
        descending = order_dir.lower() == "desc"
        letter = func.substring(order_by_attr, 1, 1)
        counts = (
            query.with_only_columns(  # type: ignore
                letter.label("letter"), func.count().label("count")
            )
            .group_by(letter)
            .order_by(letter.desc() if descending else letter.asc())
        )

        # Walk the letters in the same direction the client paginates over, so
        # each letter's offset is the count of rows that sort before it.
        result: list[tuple[str, int]] = []
        offset = 0
        for value, count in session.execute(counts).all():
            if value is not None:
                result.append((value, offset))
            offset += count
        result.sort(key=lambda entry: entry[0])
        if redis_key is not None and version is not None:
            _store_versioned_cache(redis_key, version, result)
        return result

    @begin_session
    def get_rom_id_index(
        self,
        query: Query,
        *,
        cache_key: str | None = None,
        session: Session = None,  # type: ignore
    ) -> list[int]:
        """Return every matching rom id in query order.

        The list backs the gallery's virtual scroll, so it spans the whole
        result set (not a page) and is recomputed on every request. Building it
        runs the sibling-dedup window over the full library, so the unscoped
        case is memoised under the same versioned cache as the other gallery
        sidecars.
        """
        redis_key: str | None = None
        version: str | None = None
        if cache_key:
            version = _filter_values_cache_version()
            redis_key = f"rom_id_index:{cache_key}:v{version}"
            cached = sync_cache.get(redis_key)
            if cached is not None:
                return json.loads(cached)

        ids = list(session.scalars(query.with_only_columns(Rom.id)).all())  # type: ignore

        if redis_key is not None and version is not None:
            _store_versioned_cache(redis_key, version, ids)
        return ids

    @begin_session
    def get_roms_by_fs_name(
        self,
        platform_id: int,
        fs_names: Iterable[str],
        session: Session = None,  # type: ignore
    ) -> dict[str, Rom]:
        """Retrieve a dictionary of roms by their filesystem names.

        Eager-loads only `platform` (used downstream by the scan loop via
        `rom.platform_slug` / `rom.platform.fs_slug`). This deliberately
        avoids `with_details`, whose full relationship eager-load is
        wasted work for the scan-skip decision on large platforms.
        """
        roms = (
            session.scalars(
                select(Rom)
                .options(
                    selectinload(Rom.platform),
                )
                .where(
                    and_(
                        Rom.platform_id == platform_id,
                        Rom.fs_name.in_(fs_names),
                    )
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
        if "name" in data and "name_sort_key" not in data:
            # Re-derive the key from the new name, but only when the stored key
            # is still the derived value (i.e. not a manual override). Mirrors
            # the `@validates` logic, which the bulk update() bypasses.
            existing = session.query(Rom).filter_by(id=id).one()
            if (
                existing.name_sort_key is None
                or existing.name_sort_key == compute_name_sort_key(existing.name)
            ):
                data = {**data, "name_sort_key": compute_name_sort_key(data["name"])}

        if "fs_name" in data:
            parts = compute_file_name_parts(data["fs_name"])
            data = {
                **data,
                "fs_name_no_tags": parts.no_tags,
                "fs_name_no_ext": parts.no_ext,
                "fs_extension": parts.extension,
            }

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
    def bulk_mark_present(
        self,
        platform_id: int,
        rom_ids: list[int],
        session: Session = None,  # type: ignore
    ) -> None:
        """Bulk set missing_from_fs=False for a list of ROM IDs."""
        if not rom_ids:
            return

        for i in range(0, len(rom_ids), 1000):
            chunk = rom_ids[i : i + 1000]
            session.execute(
                update(Rom)
                .where(
                    and_(
                        Rom.platform_id == platform_id,
                        Rom.id.in_(chunk),
                    )
                )
                .values(missing_from_fs=False)
                .execution_options(synchronize_session="evaluate")
            )

    @begin_session
    def mark_missing_roms(
        self,
        platform_id: int,
        fs_roms_to_keep: list[str],
        session: Session = None,  # type: ignore
    ) -> Sequence[Rom]:
        """Sync `missing_from_fs` for a platform against the keep-list.

        Reads the rows once and writes only those whose state actually
        changes, so a re-scan of an unchanged platform issues no updates.
        """
        keep_set = set(fs_roms_to_keep)
        rows = session.execute(
            select(Rom.id, Rom.fs_name, Rom.missing_from_fs).where(
                Rom.platform_id == platform_id
            )
        ).all()

        flips: dict[bool, list[int]] = {True: [], False: []}
        for rom_id, fs_name, was_missing in rows:
            is_missing = fs_name not in keep_set
            if is_missing != was_missing:
                flips[is_missing].append(rom_id)

        for desired, ids in flips.items():
            for i in range(0, len(ids), 1000):
                session.execute(
                    update(Rom)
                    .where(Rom.id.in_(ids[i : i + 1000]))
                    .values(missing_from_fs=desired)
                    .execution_options(synchronize_session="evaluate")
                )

        return (
            session.scalars(
                select(Rom)
                .options(load_only(Rom.id, Rom.fs_name))
                .where(
                    and_(
                        Rom.platform_id == platform_id,
                        Rom.missing_from_fs.is_(True),
                    )
                )
                .order_by(Rom.fs_name.asc())
            )
            .unique()
            .all()
        )

    @begin_session
    def add_rom_user(
        self,
        rom_id: int,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> RomUser:
        rom_user = session.merge(RomUser(rom_id=rom_id, user_id=user_id))
        session.flush()
        return rom_user

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

        rom_user = session.query(RomUser).filter_by(id=id).one_or_none()
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

        return rom_user

    @begin_session
    def add_rom_file(
        self,
        rom_file: RomFile,
        session: Session = None,  # type: ignore
    ) -> RomFile:
        merged = session.merge(rom_file)
        session.flush()
        return merged

    @begin_session
    def get_rom_file_by_id(
        self,
        id: int,
        session: Session = None,  # type: ignore
    ) -> RomFile | None:
        return session.scalar(select(RomFile).filter_by(id=id).limit(1))

    @begin_session
    def get_rom_file_by_path(
        self,
        rom_id: int,
        file_path: str,
        file_name: str,
        session: Session = None,  # type: ignore
    ) -> RomFile | None:
        return session.scalar(
            select(RomFile)
            .filter_by(rom_id=rom_id, file_path=file_path, file_name=file_name)
            .limit(1)
        )

    @begin_session
    def get_rom_files_by_category(
        self,
        rom_id: int,
        category: RomFileCategory,
        session: Session = None,  # type: ignore
    ) -> Sequence[RomFile]:
        """Return the ROM's files for a single category, ordered by file_name."""
        return (
            session.scalars(
                select(RomFile)
                .filter_by(rom_id=rom_id, category=category)
                .order_by(RomFile.file_name.asc())
            )
            .unique()
            .all()
        )

    @begin_session
    def rom_files_for_rom_id(
        self,
        rom_id: int,
        session: Session = None,  # type: ignore
    ) -> list[RomFile]:
        """Fetch a ROM's files on demand, with the `RomFile.rom` backref loaded."""
        return list(
            session.scalars(
                select(RomFile)
                .filter_by(rom_id=rom_id)
                .options(joinedload(RomFile.rom).load_only(Rom.fs_path, Rom.fs_name))
            )
            .unique()
            .all()
        )

    @begin_session
    def update_rom_file(
        self,
        id: int,
        data: dict,
        session: Session = None,  # type: ignore
    ) -> RomFile | None:
        session.execute(
            update(RomFile)
            .where(RomFile.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

        return session.query(RomFile).filter_by(id=id).one_or_none()

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

    @begin_session
    def delete_rom_file(
        self,
        id: int,
        session: Session = None,  # type: ignore
    ) -> None:
        session.execute(
            delete(RomFile)
            .where(RomFile.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    # Note management methods
    @begin_session
    def get_rom_notes(
        self,
        rom_id: int,
        user_id: int,
        public_only: bool = False,
        search: str | None = "",
        tags: list[str] | None = None,
        only_fields: Sequence[QueryableAttribute] | None = None,
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

        if only_fields:
            query = query.options(load_only(*only_fields))

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
        crc_hash: str | None = None,
        md5_hash: str | None = None,
        sha1_hash: str | None = None,
        ra_hash: str | None = None,
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
                (ra_hash, Rom.ra_hash),
                (crc_hash, RomFile.crc_hash),
                (md5_hash, RomFile.md5_hash),
                (sha1_hash, RomFile.sha1_hash),
                (ra_hash, RomFile.ra_hash),
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

    def invalidate_filter_values_cache(self) -> None:
        old_version = str(int(sync_cache.incr(ROM_FILTERS_CACHE_VERSION_KEY)) - 1)
        old_keys_set = _filter_values_cache_keys_key(old_version)
        old_cache_keys = [
            key
            for raw_key in sync_cache.smembers(old_keys_set)
            if (key := _cache_value_to_str(raw_key)) is not None
        ]
        if old_cache_keys:
            sync_cache.delete(*old_cache_keys)
        sync_cache.delete(old_keys_set)

    @begin_session
    def with_filter_values(
        self,
        query: Query,
        *,
        cache_key: str | None = None,
        session: Session = None,  # type: ignore
    ) -> dict:
        """
        Returns the list of filters given the current subset of ROMs in the query
        """
        redis_key: str | None = None
        version: str | None = None
        if cache_key:
            version = _filter_values_cache_version()
            redis_key = f"filter_values:{cache_key}:v{version}"
            cached = sync_cache.get(redis_key)
            if cached is not None:
                return json.loads(cached)

        ids_subq = query.order_by(None).with_only_columns(Rom.id).scalar_subquery()  # type: ignore

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

        result = self._collect_filter_values(session, statement)
        if redis_key is not None and version is not None:
            _store_versioned_cache(redis_key, version, result)
        return result

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
