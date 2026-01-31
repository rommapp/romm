from collections.abc import Sequence

from sqlalchemy import and_, delete, desc, select, update
from sqlalchemy.orm import QueryableAttribute, Session, load_only

from decorators.database import begin_session
from models.assets import Save
from models.rom import Rom

from .base_handler import DBBaseHandler


class DBSavesHandler(DBBaseHandler):
    @begin_session
    def add_save(
        self,
        save: Save,
        session: Session = None,  # type: ignore
    ) -> Save:
        return session.merge(save)

    @begin_session
    def get_save(
        self,
        user_id: int,
        id: int,
        session: Session = None,  # type: ignore
    ) -> Save | None:
        return session.scalar(select(Save).filter_by(user_id=user_id, id=id).limit(1))

    @begin_session
    def get_save_by_filename(
        self,
        user_id: int,
        rom_id: int,
        file_name: str,
        session: Session = None,  # type: ignore
    ) -> Save | None:
        return session.scalars(
            select(Save)
            .filter_by(rom_id=rom_id, user_id=user_id, file_name=file_name)
            .limit(1)
        ).first()

    @begin_session
    def get_save_by_content_hash(
        self,
        user_id: int,
        rom_id: int,
        content_hash: str,
        session: Session = None,  # type: ignore
    ) -> Save | None:
        return session.scalar(
            select(Save)
            .filter_by(rom_id=rom_id, user_id=user_id, content_hash=content_hash)
            .limit(1)
        )

    @begin_session
    def get_saves(
        self,
        user_id: int,
        rom_id: int | None = None,
        platform_id: int | None = None,
        slot: str | None = None,
        order_by_updated_at_desc: bool = False,
        only_fields: Sequence[QueryableAttribute] | None = None,
        session: Session = None,  # type: ignore
    ) -> Sequence[Save]:
        query = select(Save).filter_by(user_id=user_id)

        if rom_id:
            query = query.filter_by(rom_id=rom_id)

        if platform_id:
            query = query.join(Rom, Save.rom_id == Rom.id).filter(
                Rom.platform_id == platform_id
            )

        if slot is not None:
            query = query.filter(Save.slot == slot)

        if order_by_updated_at_desc:
            query = query.order_by(desc(Save.updated_at))

        if only_fields:
            query = query.options(load_only(*only_fields))

        return session.scalars(query).all()

    @begin_session
    def update_save(
        self,
        id: int,
        data: dict,
        session: Session = None,  # type: ignore
    ) -> Save:
        session.execute(
            update(Save)
            .where(Save.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )
        return session.query(Save).filter_by(id=id).one()

    @begin_session
    def delete_save(
        self,
        id: int,
        session: Session = None,  # type: ignore
    ) -> None:
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
        session: Session = None,  # type: ignore
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

    @begin_session
    def get_saves_summary(
        self,
        user_id: int,
        rom_id: int,
        session: Session = None,  # type: ignore
    ) -> dict:
        saves = session.scalars(
            select(Save)
            .filter_by(user_id=user_id, rom_id=rom_id)
            .order_by(desc(Save.updated_at))
        ).all()

        slots_data: dict[str | None, dict] = {}
        for save in saves:
            slot_key = save.slot
            if slot_key not in slots_data:
                slots_data[slot_key] = {"slot": slot_key, "count": 0, "latest": save}
            slots_data[slot_key]["count"] += 1

        return {
            "total_count": len(saves),
            "slots": list(slots_data.values()),
        }
