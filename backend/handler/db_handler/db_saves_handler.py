from decorators.database import begin_session
from handler.db_handler.db_handler import DBHandler
from models import Save, Rom
from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.orm import Session


class DBSavesHandler(DBHandler):
    # @staticmethod
    # def _filter(data, platform_id, search_term):
    #     if platform_id:
    #         data = data.filter_by(platform_id=platform_id)
    #     if search_term:
    #         data = data.filter(Rom.file_name.ilike(f"%{search_term}%"))
    #     return data

    # @staticmethod
    # def _order(data, order_by, order_dir):
    #     if order_by == "name":
    #         _column = func.lower(Rom.name)
    #     elif order_by == "id":
    #         _column = Rom.id
    #     else:
    #         _column = func.lower(Rom.name)

    #     if order_dir == "asc":
    #         return data.order_by(_column.asc())
    #     elif order_dir == "desc":
    #         return data.order_by(_column.desc())
    #     else:
    #         return data.order_by(_column.asc())

    @begin_session
    def add_save(self, save: Save, session: Session = None):
        return session.merge(save)

    @begin_session
    def get_save(self, id: int, session: Session = None):
        return session.get(Save, id)

    @begin_session
    def update_save(self, id: int, data: dict, session: Session = None):
        session.execute(
            update(Save)
            .where(Save.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def delete_save(self, id: int, session: Session = None):
        return session.execute(
            delete(Save)
            .where(Save.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def purge_saves(self, platform_id: int, saves: list[str], session: Session = None):
        return session.execute(
            delete(Save)
            .where(and_(Save.platform_id == platform_id, Save.file_name.not_in(saves)))
            .execution_options(synchronize_session="evaluate")
        )
