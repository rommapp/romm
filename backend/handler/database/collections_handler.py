from collections.abc import Sequence
from typing import Any

from decorators.database import begin_session
from models.collection import (
    Collection,
    CollectionRom,
    SmartCollection,
    VirtualCollection,
)
from models.rom import Rom
from sqlalchemy import and_, delete, insert, literal, or_, select, update
from sqlalchemy.orm import Session

from .base_handler import DBBaseHandler


class DBCollectionsHandler(DBBaseHandler):
    @begin_session
    def add_collection(
        self, collection: Collection, session: Session = None
    ) -> Collection:
        collection = session.merge(collection)
        session.flush()

        return session.query(Collection).filter_by(id=collection.id).one()

    @begin_session
    def get_collection(self, id: int, session: Session = None) -> Collection | None:
        return session.scalar(select(Collection).filter_by(id=id).limit(1))

    @begin_session
    def get_virtual_collection(
        self, id: str, session: Session = None
    ) -> VirtualCollection | None:
        name, type = VirtualCollection.from_id(id)
        return session.scalar(
            select(VirtualCollection).filter_by(name=name, type=type).limit(1)
        )

    @begin_session
    def get_collection_by_name(
        self, name: str, user_id: int, session: Session = None
    ) -> Collection | None:
        return session.scalar(
            select(Collection).filter_by(name=name, user_id=user_id).limit(1)
        )

    @begin_session
    def get_collections(self, session: Session = None) -> Sequence[Collection]:
        return (
            session.scalars(select(Collection).order_by(Collection.name.asc()))
            .unique()
            .all()
        )

    @begin_session
    def get_virtual_collections(
        self, type: str, limit: int | None = None, session: Session = None
    ) -> Sequence[VirtualCollection]:
        return (
            session.scalars(
                select(VirtualCollection)
                .filter(or_(VirtualCollection.type == type, literal(type == "all")))
                .limit(limit)
                .order_by(VirtualCollection.name.asc())
            )
            .unique()
            .all()
        )

    @begin_session
    def update_collection(
        self,
        id: int,
        data: dict,
        rom_ids: list[int] | None = None,
        session: Session = None,
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
                session.execute(
                    insert(CollectionRom),
                    [
                        {"collection_id": id, "rom_id": rom_id}
                        for rom_id in set(rom_ids)
                    ],
                )

        return session.query(Collection).filter_by(id=id).one()

    @begin_session
    def delete_collection(self, id: int, session: Session = None) -> None:
        session.execute(
            delete(Collection)
            .where(Collection.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    # Smart Collection methods
    @begin_session
    def add_smart_collection(
        self, smart_collection: SmartCollection, session: Session = None
    ) -> SmartCollection:
        smart_collection = session.merge(smart_collection)
        session.flush()

        return session.query(SmartCollection).filter_by(id=smart_collection.id).one()

    @begin_session
    def get_smart_collection(
        self, id: int, session: Session = None
    ) -> SmartCollection | None:
        return session.scalar(select(SmartCollection).filter_by(id=id).limit(1))

    @begin_session
    def get_smart_collection_by_name(
        self, name: str, user_id: int, session: Session = None
    ) -> SmartCollection | None:
        return session.scalar(
            select(SmartCollection).filter_by(name=name, user_id=user_id).limit(1)
        )

    @begin_session
    def get_smart_collections(
        self, user_id: int | None = None, session: Session = None
    ) -> Sequence[SmartCollection]:
        query = select(SmartCollection).order_by(SmartCollection.name.asc())

        if user_id is not None:
            # Get user's smart collections and public ones
            query = query.filter(
                (SmartCollection.user_id == user_id) | SmartCollection.is_public
            )

        return session.scalars(query).unique().all()

    def _update_smart_collection_with_optimistic_lock(
        self, session: Session, smart_collection: SmartCollection, data: dict[str, Any]
    ) -> bool:
        """Helper method to update smart collection with optimistic locking."""
        result = session.execute(
            update(SmartCollection)
            .where(
                and_(
                    SmartCollection.id == smart_collection.id,
                    SmartCollection.updated_at == smart_collection.updated_at,
                )
            )
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )
        return result.rowcount > 0

    @begin_session
    def update_smart_collection(
        self,
        id: int,
        data: dict[str, Any],
        session: Session = None,
    ) -> SmartCollection:
        # Need to get the smart collection from the current session
        smart_collection = session.get(SmartCollection, id)
        if not smart_collection:
            raise ValueError(f"SmartCollection with id {id} not found")

        if not self._update_smart_collection_with_optimistic_lock(
            session, smart_collection, data
        ):
            # Record was modified by another process, try to refresh and retry
            session.refresh(smart_collection)
            if not self._update_smart_collection_with_optimistic_lock(
                session, smart_collection, data
            ):
                raise ValueError(
                    f"SmartCollection {smart_collection.id} was modified by another process"
                )

        return session.query(SmartCollection).filter_by(id=id).one()

    @begin_session
    def delete_smart_collection(self, id: int, session: Session = None) -> None:
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

        # Use the existing filter_roms method with the stored criteria
        return db_rom_handler.get_roms_scalar(
            platform_id=criteria.get("platform_id"),
            collection_id=criteria.get("collection_id"),
            virtual_collection_id=criteria.get("virtual_collection_id"),
            search_term=criteria.get("search_term"),
            matched=criteria.get("matched"),
            favourite=criteria.get("favourite"),
            duplicate=criteria.get("duplicate"),
            playable=criteria.get("playable"),
            has_ra=criteria.get("has_ra"),
            missing=criteria.get("missing"),
            verified=criteria.get("verified"),
            selected_genre=criteria.get("selected_genre"),
            selected_franchise=criteria.get("selected_franchise"),
            selected_collection=criteria.get("selected_collection"),
            selected_company=criteria.get("selected_company"),
            selected_age_rating=criteria.get("selected_age_rating"),
            selected_status=criteria.get("selected_status"),
            selected_region=criteria.get("selected_region"),
            selected_language=criteria.get("selected_language"),
            user_id=user_id,
            order_by=criteria.get("order_by", "name"),
            order_dir=criteria.get("order_dir", "asc"),
        )
