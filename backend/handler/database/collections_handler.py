from decorators.database import begin_session
from models.collection import Collection
from models.rom import Rom
from sqlalchemy import Select, delete, or_, select
from sqlalchemy.orm import Query, Session

from .base_handler import DBBaseHandler


class DBCollectionsHandler(DBBaseHandler):
    @begin_session
    def add_collection(
        self, data: dict, query: Query = None, session: Session = None
    ) -> Collection | None:
        collection = session.merge(**data)
        session.flush()

        return session.scalar(query.filter_by(id=collection.id).limit(1))

    @begin_session
    def get_collection(
        self, id: int, *, query: Query = None, session: Session = None
    ) -> Collection | None:
        return session.scalar(query.filter_by(id=id).limit(1))

    @begin_session
    def get_collections(self, *, session: Session = None) -> Select[tuple[Collection]]:
        return (
            session.scalars(select(Collection).order_by(Collection.name.asc()))  # type: ignore[attr-defined]
            .unique()
            .all()
        )

    @begin_session
    def delete_collection(self, id: int, session: Session = None) -> int:
        return session.execute(
            delete(Collection)
            .where(Collection.id == id)
            .execution_options(synchronize_session="evaluate")
        )
