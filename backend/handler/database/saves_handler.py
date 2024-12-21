from typing import Sequence

from decorators.database import begin_session
from models.assets import Save
from sqlalchemy import and_, delete, select, update
from sqlalchemy.orm import Session

from .base_handler import DBBaseHandler


class DBSavesHandler(DBBaseHandler):
    @begin_session
    def add_save(self, save: Save, session: Session = None) -> Save:
        return session.merge(save)

    @begin_session
    def get_save(self, id: int, session: Session = None) -> Save | None:
        return session.get(Save, id)

    @begin_session
    def get_save_by_filename(
        self, rom_id: int, user_id: int, file_name: str, session: Session = None
    ) -> Save | None:
        return session.scalars(
            select(Save)
            .filter_by(rom_id=rom_id, user_id=user_id, file_name=file_name)
            .limit(1)
        ).first()

    @begin_session
    def update_save(self, id: int, data: dict, session: Session = None) -> Save:
        return session.scalar(
            update(Save)
            .where(Save.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def delete_save(self, id: int, session: Session = None) -> None:
        session.execute(
            delete(Save)
            .where(Save.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def purge_saves(
        self, rom_id: int, user_id: int, saves: list[str], session: Session = None
    ) -> Sequence[Save]:
        purged_saves = session.scalars(
            select(Save).filter(
                and_(
                    Save.rom_id == rom_id,
                    Save.user_id == user_id,
                    Save.file_name.not_in(saves),
                )
            )
        ).all()

        session.execute(
            delete(Save)
            .where(
                and_(
                    Save.rom_id == rom_id,
                    Save.user_id == user_id,
                    Save.file_name.not_in(saves),
                )
            )
            .execution_options(synchronize_session="evaluate")
        )

        return purged_saves
