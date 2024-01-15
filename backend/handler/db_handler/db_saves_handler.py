from decorators.database import begin_session
from handler.db_handler.db_handler import DBHandler
from models import Save
from sqlalchemy import and_, delete, update
from sqlalchemy.orm import Session


class DBSavesHandler(DBHandler):
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
