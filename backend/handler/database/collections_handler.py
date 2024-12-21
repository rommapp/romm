from typing import Sequence

from decorators.database import begin_session
from models.collection import Collection
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from .base_handler import DBBaseHandler


class DBCollectionsHandler(DBBaseHandler):
    @begin_session
    def add_collection(
        self, collection: Collection, session: Session = None
    ) -> Collection:
        collection = session.merge(collection)
        session.flush()

        new_collection = session.scalar(
            select(Collection).filter_by(id=collection.id).limit(1)
        )
        if not new_collection:
            raise ValueError("Could not find newly created collection")

        return new_collection

    @begin_session
    def get_collection(self, id: int, session: Session = None) -> Collection | None:
        return session.scalar(select(Collection).filter_by(id=id).limit(1))

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
    def get_collections_by_rom_id(
        self, rom_id: int, session: Session = None
    ) -> Sequence[Collection]:
        return session.scalars(
            select(Collection).filter(Collection.roms.contains(rom_id))
        ).all()

    @begin_session
    def update_collection(
        self, id: int, data: dict, session: Session = None
    ) -> Collection:
        session.execute(
            update(Collection)
            .where(Collection.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )
        return session.query(Collection).filter_by(id=id).one()

    @begin_session
    def delete_collection(self, id: int, session: Session = None) -> None:
        session.execute(
            delete(Collection)
            .where(Collection.id == id)
            .execution_options(synchronize_session="evaluate")
        )
