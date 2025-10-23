from collections.abc import Sequence

from sqlalchemy import and_, delete, select, update
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.assets import Save
from models.rom import Rom

from .base_handler import DBBaseHandler


class DBSavesHandler(DBBaseHandler):
    @begin_session
    def add_save(self, save: Save, session: Session = None) -> Save:
        return session.merge(save)

    @begin_session
    def get_save(self, user_id: int, id: int, session: Session = None) -> Save | None:
        return session.scalar(select(Save).filter_by(user_id=user_id, id=id).limit(1))

    @begin_session
    def get_save_by_filename(
        self, user_id: int, rom_id: int, file_name: str, session: Session = None
    ) -> Save | None:
        return session.scalars(
            select(Save)
            .filter_by(rom_id=rom_id, user_id=user_id, file_name=file_name)
            .limit(1)
        ).first()

    @begin_session
    def get_saves(
        self,
        user_id: int,
        rom_id: int | None = None,
        platform_id: int | None = None,
        session: Session = None,
    ) -> Sequence[Save]:
        query = select(Save).filter_by(user_id=user_id)

        if rom_id:
            query = query.filter_by(rom_id=rom_id)

        if platform_id:
            query = query.join(Rom, Save.rom_id == Rom.id).filter(
                Rom.platform_id == platform_id
            )

        return session.scalars(query).all()

    @begin_session
    def update_save(self, id: int, data: dict, session: Session = None) -> Save:
        session.execute(
            update(Save)
            .where(Save.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )
        return session.query(Save).filter_by(id=id).one()

    @begin_session
    def delete_save(self, id: int, session: Session = None) -> None:
        session.execute(
            delete(Save)
            .where(Save.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def mark_missing_saves(
        self,
        rom_id: int,
        user_id: int,
        saves_to_keep: list[str],
        session: Session = None,
    ) -> Sequence[Save]:
        missing_saves = session.scalars(
            select(Save).filter(
                and_(
                    Save.rom_id == rom_id,
                    Save.user_id == user_id,
                    Save.file_name.not_in(saves_to_keep),
                )
            )
        ).all()

        session.execute(
            update(Save)
            .where(
                and_(
                    Save.rom_id == rom_id,
                    Save.user_id == user_id,
                    Save.file_name.not_in(saves_to_keep),
                )
            )
            .values(**{"missing_from_fs": True})
            .execution_options(synchronize_session="evaluate")
        )

        return missing_saves
