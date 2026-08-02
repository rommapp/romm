import functools
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Select,
    delete,
    insert,
    literal,
    or_,
    select,
    union_all,
    update,
)
from sqlalchemy.engine import Row
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (
    Query,
    QueryableAttribute,
    Session,
    load_only,
    noload,
    selectinload,
)

from config import FRONTEND_RESOURCES_PATH
from decorators.database import begin_session
from models.collection import (
    SMART_COLLECTION_MAX_COVERS,
    Collection,
    CollectionRom,
    SmartCollection,
    VirtualCollection,
    VirtualCollectionRom,
)
from models.rom import Rom
from utils.database import json_array_contains_value

from .base_handler import DBBaseHandler

MAX_VIRTUAL_COLLECTION_COVERS = 5

# Collections per UNION ALL statement, to keep any single statement small.
COVERS_BATCH_SIZE = 100


def with_roms(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        kwargs["query"] = select(Collection).options(
            selectinload(Collection.roms)
            .load_only(
                Rom.id,
                Rom.path_cover_s,
                Rom.path_cover_l,
            )
            .options(noload(Rom.platform), noload(Rom.metadatum))
        )
        return func(*args, **kwargs)

    return wrapper


class DBCollectionsHandler(DBBaseHandler):
    @begin_session
    @with_roms
    def add_collection(
        self,
        collection: Collection,
        query: Query = None,  # type: ignore
        session: Session = None,  # type: ignore
    ) -> Collection:
        collection = session.merge(collection)
        session.flush()

        return session.scalar(query.filter_by(id=collection.id).limit(1))

    @begin_session
    @with_roms
    def get_collection(
        self,
        id: int,
        query: Query = None,  # type: ignore
        session: Session = None,  # type: ignore
    ) -> Collection | None:
        return session.scalar(query.filter_by(id=id).limit(1))

    @begin_session
    @with_roms
    def get_collection_by_name(
        self,
        name: str,
        user_id: int,
        query: Query = None,  # type: ignore
        session: Session = None,  # type: ignore
    ) -> Collection | None:
        return session.scalar(query.filter_by(name=name, user_id=user_id).limit(1))

    @begin_session
    @with_roms
    def get_favorite_collection(
        self,
        user_id: int,
        query: Query = None,  # type: ignore
        session: Session = None,  # type: ignore
    ) -> Collection | None:
        return session.scalar(
            query.filter_by(is_favorite=True, user_id=user_id).limit(1)
        )

    @begin_session
    @with_roms
    def get_collections(
        self,
        updated_after: datetime | None = None,
        only_fields: Sequence[QueryableAttribute] | None = None,
        query: Query = None,  # type: ignore
        session: Session = None,  # type: ignore
    ) -> Sequence[Collection]:
        if updated_after:
            query = query.filter(Collection.updated_at > updated_after)

        if only_fields:
            query = query.options(load_only(*only_fields))

        return session.scalars(query.order_by(Collection.name.asc())).unique().all()

    @begin_session
    @with_roms
    def update_collection(
        self,
        id: int,
        data: dict,
        rom_ids: list[int] | None = None,
        query: Query = None,  # type: ignore
        session: Session = None,  # type: ignore
    ) -> Collection:
        session.execute(
            update(Collection)
            .where(Collection.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

        if rom_ids is not None:
            # Delete all existing CollectionRom entries for this collection
            session.execute(
                delete(CollectionRom).where(CollectionRom.collection_id == id)
            )
            # Insert new CollectionRom entries for this collection
            if rom_ids:
                # Filter out rom_ids that no longer exist in the roms table to
                # avoid foreign key constraint violations (e.g. after a rescan)
                valid_rom_ids = set(
                    session.scalars(select(Rom.id).where(Rom.id.in_(rom_ids))).all()
                )
                if valid_rom_ids:
                    session.execute(
                        insert(CollectionRom),
                        [
                            {"collection_id": id, "rom_id": rom_id}
                            for rom_id in valid_rom_ids
                        ],
                    )

        return session.scalar(query.filter_by(id=id).limit(1))

    @begin_session
    @with_roms
    def add_roms_to_collection(
        self,
        id: int,
        rom_ids: list[int],
        query: Query = None,  # type: ignore
        session: Session = None,  # type: ignore
    ) -> Collection:
        if rom_ids:
            valid_rom_ids = set(
                session.scalars(select(Rom.id).where(Rom.id.in_(rom_ids))).all()
            )
            existing_ids = set(
                session.scalars(
                    select(CollectionRom.rom_id).where(
                        CollectionRom.collection_id == id
                    )
                ).all()
            )
            new_ids = valid_rom_ids - existing_ids
            if new_ids:
                try:
                    with session.begin_nested():
                        session.execute(
                            insert(CollectionRom),
                            [
                                {"collection_id": id, "rom_id": rom_id}
                                for rom_id in new_ids
                            ],
                        )
                except IntegrityError:
                    # Concurrent request inserted the same rows; data is consistent
                    pass
                session.execute(
                    update(Collection)
                    .where(Collection.id == id)
                    .values(updated_at=datetime.now(timezone.utc))
                    .execution_options(synchronize_session="evaluate")
                )

        return session.scalar(query.filter_by(id=id).limit(1))

    @begin_session
    @with_roms
    def remove_roms_from_collection(
        self,
        id: int,
        rom_ids: list[int],
        query: Query = None,  # type: ignore
        session: Session = None,  # type: ignore
    ) -> Collection:
        if rom_ids:
            result = session.execute(
                delete(CollectionRom).where(
                    CollectionRom.collection_id == id,
                    CollectionRom.rom_id.in_(rom_ids),
                )
            )
            if result.rowcount > 0:
                session.execute(
                    update(Collection)
                    .where(Collection.id == id)
                    .values(updated_at=datetime.now(timezone.utc))
                    .execution_options(synchronize_session="evaluate")
                )

        return session.scalar(query.filter_by(id=id).limit(1))

    @begin_session
    def delete_collection(
        self,
        id: int,
        session: Session = None,  # type: ignore
    ) -> None:
        session.execute(
            delete(Collection)
            .where(Collection.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    # Virtual collections
    def _attach_covers(
        self,
        session: Session,
        collections: Sequence[VirtualCollection],
    ) -> None:
        """Fill in each collection's covers from its membership rows.

        The view deliberately doesn't aggregate covers: on a large library that
        is megabytes of cover paths per request, while callers render a handful.

        Each collection gets its own primary-key lookup capped at
        MAX_VIRTUAL_COLLECTION_COVERS rows, batched into UNION ALL statements,
        so the cost follows the number of collections rather than the size of
        the library.
        """
        if not collections:
            return

        def covers_select(collection: VirtualCollection) -> Select:
            return (
                select(
                    VirtualCollectionRom.type,
                    VirtualCollectionRom.name,
                    VirtualCollectionRom.path_cover_s,
                    VirtualCollectionRom.path_cover_l,
                )
                .where(
                    VirtualCollectionRom.type == collection.type,
                    VirtualCollectionRom.name == collection.name,
                    or_(
                        VirtualCollectionRom.path_cover_s != "",
                        VirtualCollectionRom.path_cover_l != "",
                    ),
                )
                .order_by(VirtualCollectionRom.rom_id)
                .limit(MAX_VIRTUAL_COLLECTION_COVERS)
            )

        covers: dict[tuple[str, str], tuple[list[str], list[str]]] = {}
        for start in range(0, len(collections), COVERS_BATCH_SIZE):
            batch = collections[start : start + COVERS_BATCH_SIZE]
            selects = [covers_select(collection) for collection in batch]
            statement = selects[0] if len(selects) == 1 else union_all(*selects)

            for row in session.execute(statement).all():
                small, large = covers.setdefault((row.type, row.name), ([], []))
                if row.path_cover_s:
                    small.append(row.path_cover_s)
                if row.path_cover_l:
                    large.append(row.path_cover_l)

        for collection in collections:
            small, large = covers.get((collection.type, collection.name), ([], []))
            collection.path_covers_s = small
            collection.path_covers_l = large

    @begin_session
    def get_virtual_collection(
        self,
        id: str,
        session: Session = None,  # type: ignore
    ) -> VirtualCollection | None:
        name, type = VirtualCollection.from_id(id)
        collection = session.scalar(
            select(VirtualCollection).filter_by(name=name, type=type).limit(1)
        )
        if collection:
            self._attach_covers(session, [collection])

        return collection

    @begin_session
    def get_virtual_collections(
        self,
        type: str,
        limit: int | None = None,
        only_fields: Sequence[QueryableAttribute] | None = None,
        session: Session = None,  # type: ignore
    ) -> Sequence[VirtualCollection]:
        query = (
            select(VirtualCollection)
            .filter(or_(VirtualCollection.type == type, literal(type == "all")))
            .limit(limit)
            .order_by(VirtualCollection.name.asc())
        )

        if only_fields:
            # Identifier-only callers never render covers.
            query = query.options(load_only(*only_fields))
            return session.scalars(query).unique().all()

        collections = session.scalars(query).unique().all()
        self._attach_covers(session, collections)

        return collections

    def get_virtual_collection_rom_ids(self, id: str) -> Select:
        """Select the rom ids of a virtual collection, as an indexed subquery."""
        name, type = VirtualCollection.from_id(id)
        return select(VirtualCollectionRom.rom_id).where(
            VirtualCollectionRom.type == type, VirtualCollectionRom.name == name
        )

    # Smart collections
    @begin_session
    def add_smart_collection(
        self,
        smart_collection: SmartCollection,
        session: Session = None,  # type: ignore
    ) -> SmartCollection:
        smart_collection = session.merge(smart_collection)
        session.flush()

        return session.query(SmartCollection).filter_by(id=smart_collection.id).one()

    @begin_session
    def get_smart_collection(
        self,
        id: int,
        session: Session = None,  # type: ignore
    ) -> SmartCollection | None:
        return session.scalar(select(SmartCollection).filter_by(id=id).limit(1))

    @begin_session
    def get_smart_collection_by_name(
        self,
        name: str,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> SmartCollection | None:
        return session.scalar(
            select(SmartCollection).filter_by(name=name, user_id=user_id).limit(1)
        )

    @begin_session
    def get_smart_collections(
        self,
        user_id: int | None = None,
        updated_after: datetime | None = None,
        only_fields: Sequence[QueryableAttribute] | None = None,
        session: Session = None,  # type: ignore
    ) -> Sequence[SmartCollection]:
        query = select(SmartCollection).order_by(SmartCollection.name.asc())

        if user_id is not None:
            # Get user's smart collections and public ones
            query = query.filter(
                (SmartCollection.user_id == user_id) | SmartCollection.is_public
            )

        if updated_after:
            query = query.filter(SmartCollection.updated_at > updated_after)

        if only_fields:
            query = query.options(load_only(*only_fields))

        return session.scalars(query).unique().all()

    @begin_session
    def get_smart_collections_for_rom(
        self,
        rom_id: int,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> Sequence[SmartCollection]:
        # Membership is a cached JSON array of rom ids on the collection, so
        # push containment + visibility into SQL rather than loading every
        # collection's rom_ids blob into Python and scanning it (see #3934).
        return (
            session.scalars(
                select(SmartCollection)
                .where(
                    json_array_contains_value(
                        SmartCollection.rom_ids, rom_id, session=session
                    ),
                    or_(
                        SmartCollection.user_id == user_id,
                        SmartCollection.is_public,
                    ),
                )
                .options(
                    load_only(
                        SmartCollection.id,
                        SmartCollection.name,
                        SmartCollection.is_public,
                    )
                )
                .order_by(SmartCollection.name.asc())
            )
            .unique()
            .all()
        )

    @begin_session
    def update_smart_collection(
        self,
        id: int,
        data: dict[str, Any],
        session: Session = None,  # type: ignore
    ) -> SmartCollection:
        session.execute(
            update(SmartCollection)
            .where(SmartCollection.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

        return session.query(SmartCollection).filter_by(id=id).one()

    @begin_session
    def delete_smart_collection(
        self,
        id: int,
        session: Session = None,  # type: ignore
    ) -> None:
        session.execute(
            delete(SmartCollection)
            .where(SmartCollection.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    def get_smart_collection_criteria(
        self, smart_collection: SmartCollection
    ) -> dict[str, Any]:
        """Translate stored filter criteria into `filter_roms` keyword arguments.

        `smart_collection_id` is dropped: the create dialog records the route it
        was opened from, so a smart collection built while viewing another one
        carries that id, and following it would nest (and could cycle).
        """
        criteria = smart_collection.filter_criteria

        # Early versions stored single values under `selected_*` keys.
        def as_list(new_key: str, old_key: str) -> list[str] | None:
            value = criteria.get(new_key) or criteria.get(old_key)
            if not value:
                return None
            return value if isinstance(value, list) else [value]

        platform_ids = criteria.get("platform_ids")
        if platform_ids is None and (platform_id := criteria.get("platform_id")):
            platform_ids = [platform_id]

        return {
            "platform_ids": platform_ids,
            "collection_id": criteria.get("collection_id"),
            "virtual_collection_id": criteria.get("virtual_collection_id"),
            "search_term": criteria.get("search_term"),
            "matched": criteria.get("matched"),
            "favorite": criteria.get("favorite"),
            "duplicate": criteria.get("duplicate"),
            "playable": criteria.get("playable"),
            "has_ra": criteria.get("has_ra"),
            "has_saves": criteria.get("has_saves"),
            "has_states": criteria.get("has_states"),
            "has_soundtrack": criteria.get("has_soundtrack"),
            "missing": criteria.get("missing"),
            "verified": criteria.get("verified"),
            "genres": as_list("genres", "selected_genre"),
            "franchises": as_list("franchises", "selected_franchise"),
            "collections": as_list("collections", "selected_collection"),
            "companies": as_list("companies", "selected_company"),
            "age_ratings": as_list("age_ratings", "selected_age_rating"),
            "regions": as_list("regions", "selected_region"),
            "languages": as_list("languages", "selected_language"),
            "tags": as_list("tags", "selected_tag"),
            "statuses": as_list("statuses", "selected_status"),
            "player_counts": criteria.get("player_counts"),
            "metadata_providers": criteria.get("metadata_providers"),
            "genres_logic": criteria.get("genres_logic", "any"),
            "franchises_logic": criteria.get("franchises_logic", "any"),
            "collections_logic": criteria.get("collections_logic", "any"),
            "companies_logic": criteria.get("companies_logic", "any"),
            "age_ratings_logic": criteria.get("age_ratings_logic", "any"),
            "regions_logic": criteria.get("regions_logic", "any"),
            "languages_logic": criteria.get("languages_logic", "any"),
            "player_counts_logic": criteria.get("player_counts_logic", "any"),
            "statuses_logic": criteria.get("statuses_logic", "any"),
            "metadata_providers_logic": criteria.get("metadata_providers_logic", "any"),
            "tags_logic": criteria.get("tags_logic", "any"),
        }

    def build_smart_collection_query(
        self,
        *,
        query: Query,
        smart_collection: SmartCollection,
        user_id: int | None,
        session: Session,
    ) -> Query:
        """Apply a smart collection's stored criteria to a ROM query.

        The criteria are `filter_roms`'s own vocabulary, so membership composes
        into SQL and the database can return just the page being viewed, rather
        than the whole matching library being assembled in Python first (#4029).

        Relationships are not eager-loaded, so the result is for filtering, not
        for serializing ROMs. The caller owns the query's joins, including
        `RomUser` for the per-user criteria (favorite, statuses, saves, states).
        """
        from handler.database import db_rom_handler

        return db_rom_handler.filter_roms(
            query=query,
            user_id=user_id,
            include_related=False,
            session=session,
            **self.get_smart_collection_criteria(smart_collection),
        )

    @begin_session
    def get_smart_collection_members(
        self,
        smart_collection: SmartCollection,
        user_id: int | None = None,
        session: Session = None,  # type: ignore
    ) -> Sequence[Row[tuple[int, str | None, str | None]]]:
        """Every member's id and cover paths, in the collection's own order.

        Only the columns the cached membership needs, so refreshing never
        hydrates ROM metadata.
        """
        from handler.database import db_rom_handler

        criteria = smart_collection.filter_criteria
        query, _ = db_rom_handler.get_roms_query(
            order_by=criteria.get("order_by", "name"),
            order_dir=criteria.get("order_dir", "asc"),
            search_term=criteria.get("search_term"),
            user_id=user_id,
            session=session,
        )
        query = self.build_smart_collection_query(
            query=query,
            smart_collection=smart_collection,
            user_id=user_id,
            session=session,
        ).with_only_columns(  # type: ignore
            Rom.id, Rom.path_cover_s, Rom.path_cover_l
        )

        return session.execute(query).all()

    @begin_session
    def refresh_smart_collection(
        self,
        id: int,
        session: Session = None,  # type: ignore
    ) -> SmartCollection | None:
        """Recompute a smart collection's cached membership columns.

        Those columns back the collections list and the ROM detail page, and are
        maintained on write: when the collection changes, and when the library
        does. They describe the owner's view, since the row is shared and
        criteria like `favorite` or `has_saves` answer differently per user.
        """
        smart_collection = session.scalar(
            select(SmartCollection).filter_by(id=id).limit(1)
        )
        if not smart_collection:
            return None

        members = self.get_smart_collection_members(
            smart_collection, user_id=smart_collection.user_id, session=session
        )
        rom_ids = [member.id for member in members]
        covers_small = [
            f"{FRONTEND_RESOURCES_PATH}/{member.path_cover_s}"
            for member in members
            if member.path_cover_s
        ][:SMART_COLLECTION_MAX_COVERS]
        covers_large = [
            f"{FRONTEND_RESOURCES_PATH}/{member.path_cover_l}"
            for member in members
            if member.path_cover_l
        ][:SMART_COLLECTION_MAX_COVERS]

        # Compare without the cache-buster: it is read from `updated_at` before
        # the write bumps it, so a stored URL never carries the row's current
        # timestamp and comparing whole URLs would rewrite on every refresh.
        if (
            smart_collection.rom_ids == rom_ids
            and [u.split("?", 1)[0] for u in smart_collection.path_covers_small]
            == covers_small
            and [u.split("?", 1)[0] for u in smart_collection.path_covers_large]
            == covers_large
        ):
            return smart_collection

        timestamp = smart_collection.updated_at
        return self.update_smart_collection(
            id,
            {
                "rom_count": len(rom_ids),
                "rom_ids": rom_ids,
                "path_covers_small": [f"{c}?ts={timestamp}" for c in covers_small],
                "path_covers_large": [f"{c}?ts={timestamp}" for c in covers_large],
            },
            session=session,
        )

    @begin_session
    def refresh_smart_collections(
        self,
        session: Session = None,  # type: ignore
    ) -> int:
        """Refresh every smart collection, e.g. once the library has changed."""
        ids = session.scalars(select(SmartCollection.id)).all()
        for id in ids:
            self.refresh_smart_collection(id, session=session)

        return len(ids)

    @begin_session
    def refresh_smart_collections_for_roms(
        self,
        rom_ids: Sequence[int],
        membership_only: bool = False,
        session: Session = None,  # type: ignore
    ):
        """Refresh the collections a handful of changed ROMs touch.

        Editing one ROM rarely moves any collection, and asking whether given
        ids match is an indexed lookup, so only the collections that actually
        hold one of them pay for a recount.

        `membership_only` is for changes that leave the ROM row alone, like a
        save, a state, a status or collection membership: nothing about the ROM
        can have moved except whether it matches, so a member that stayed one
        needs no recount. That matters because autosaves land constantly. The
        default suits a library change, where a ROM that stayed a member can
        still have a new name, sort position or cover to reflect.
        """
        from handler.database import db_rom_handler

        if not rom_ids:
            return

        candidates = set(rom_ids)
        for smart_collection in session.scalars(select(SmartCollection)).all():
            matching = db_rom_handler.get_smart_collection_matches(
                smart_collection=smart_collection,
                rom_ids=candidates,
                user_id=smart_collection.user_id,
                session=session,
            )
            cached = candidates & set(smart_collection.rom_ids)
            moved = matching != cached if membership_only else bool(matching or cached)
            if moved:
                self.refresh_smart_collection(smart_collection.id, session=session)
