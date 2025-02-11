from typing import Sequence

from decorators.database import begin_session
from models.collection import Collection, CollectionRom, VirtualCollection
from sqlalchemy import delete, insert, literal, or_, select, update
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

        if rom_ids:
            # Delete all existing CollectionRom entries for this collection
            session.execute(
                delete(CollectionRom).where(CollectionRom.collection_id == id)
            )
            # Insert new CollectionRom entries for this collection
            session.execute(
                insert(CollectionRom),
                [{"collection_id": id, "rom_id": rom_id} for rom_id in set(rom_ids)],
            )

        return session.query(Collection).filter_by(id=id).one()

    @begin_session
    def delete_collection(self, id: int, session: Session = None) -> None:
        session.execute(
            delete(Collection)
            .where(Collection.id == id)
            .execution_options(synchronize_session="evaluate")
        )
