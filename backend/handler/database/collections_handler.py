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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (
    Query,
    QueryableAttribute,
    Session,
    load_only,
    noload,
    selectinload,
)

from decorators.database import begin_session
from models.collection import (
    Collection,
    CollectionRom,
    SmartCollection,
    VirtualCollection,
    VirtualCollectionRom,
)
from models.rom import Rom

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

    def get_smart_collection_roms(
        self, smart_collection: SmartCollection, user_id: int | None = None
    ) -> Sequence["Rom"]:
        """Get ROMs that match the smart collection's filter criteria."""
        from handler.database import db_rom_handler

        # Extract filter criteria
        criteria = smart_collection.filter_criteria

        # Convert legacy single-value criteria to arrays for backward compatibility
        def convert_legacy_filter(new_key: str, old_key: str) -> list[str] | None:
            """Convert legacy single-value filter to array format."""
            if new_value := criteria.get(new_key):
                return new_value if isinstance(new_value, list) else [new_value]
            if old_value := criteria.get(old_key):
                return old_value if isinstance(old_value, list) else [old_value]
            return None

        # Apply conversions
        genres = convert_legacy_filter("genres", "selected_genre")
        franchises = convert_legacy_filter("franchises", "selected_franchise")
        collections = convert_legacy_filter("collections", "selected_collection")
        companies = convert_legacy_filter("companies", "selected_company")
        publishers = convert_legacy_filter("publishers", "selected_publisher")
        developers = convert_legacy_filter("developers", "selected_developer")
        age_ratings = convert_legacy_filter("age_ratings", "selected_age_rating")
        regions = convert_legacy_filter("regions", "selected_region")
        languages = convert_legacy_filter("languages", "selected_language")
        tags = convert_legacy_filter("tags", "selected_tag")
        statuses = convert_legacy_filter("statuses", "selected_status")

        # Use the existing filter_roms method with the stored criteria
        platform_ids = criteria.get("platform_ids")
        if platform_ids is None:
            if platform_id := criteria.get("platform_id"):
                platform_ids = [platform_id]

        return db_rom_handler.get_roms_scalar(
            platform_ids=platform_ids,
            collection_id=criteria.get("collection_id"),
            virtual_collection_id=criteria.get("virtual_collection_id"),
            search_term=criteria.get("search_term"),
            matched=criteria.get("matched"),
            favorite=criteria.get("favorite"),
            duplicate=criteria.get("duplicate"),
            playable=criteria.get("playable"),
            has_ra=criteria.get("has_ra"),
            missing=criteria.get("missing"),
            verified=criteria.get("verified"),
            genres=genres,
            franchises=franchises,
            collections=collections,
            companies=companies,
            publishers=publishers,
            developers=developers,
            age_ratings=age_ratings,
            statuses=statuses,
            regions=regions,
            languages=languages,
            tags=tags,
            metadata_providers=criteria.get("metadata_providers"),
            # Logic operators for multi-value filters
            genres_logic=criteria.get("genres_logic", "any"),
            franchises_logic=criteria.get("franchises_logic", "any"),
            collections_logic=criteria.get("collections_logic", "any"),
            companies_logic=criteria.get("companies_logic", "any"),
            publishers_logic=criteria.get("publishers_logic", "any"),
            developers_logic=criteria.get("developers_logic", "any"),
            age_ratings_logic=criteria.get("age_ratings_logic", "any"),
            regions_logic=criteria.get("regions_logic", "any"),
            languages_logic=criteria.get("languages_logic", "any"),
            statuses_logic=criteria.get("statuses_logic", "any"),
            metadata_providers_logic=criteria.get("metadata_providers_logic", "any"),
            tags_logic=criteria.get("tags_logic", "any"),
            user_id=user_id,
            order_by=criteria.get("order_by", "name"),
            order_dir=criteria.get("order_dir", "asc"),
        )
