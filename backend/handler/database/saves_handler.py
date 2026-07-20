from collections.abc import Sequence
from typing import Literal

from sqlalchemy import and_, asc, delete, desc, func, or_, select, update
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
        slot: str | None = None,
        session: Session = None,  # type: ignore
    ) -> Save | None:
        query = select(Save).filter_by(
            rom_id=rom_id, user_id=user_id, file_name=file_name
        )
        # `slot=None` scopes to the null-slot save, not "any slot", so a
        # slot-less upload can never match (and overwrite) a save living in a
        # named slot.
        if slot is not None:
            query = query.filter(Save.slot == slot)
        else:
            query = query.filter(Save.slot.is_(None))
        return session.scalars(query.limit(1)).first()

    @begin_session
    def get_save_by_content_hash(
        self,
        user_id: int,
        rom_id: int,
        content_hash: str,
        slot: str | None = None,
        session: Session = None,  # type: ignore
    ) -> Save | None:
        query = select(Save).filter_by(
            rom_id=rom_id, user_id=user_id, content_hash=content_hash
        )
        if slot is not None:
            query = query.filter(Save.slot == slot)
        return session.scalar(query.limit(1))

    @begin_session
    def get_saves(
        self,
        user_id: int,
        rom_id: int | None = None,
        platform_id: int | None = None,
        slot: str | None = None,
        slot_not_null: bool = False,
        order_by: Literal["updated_at", "created_at"] | None = None,
        order_dir: Literal["asc", "desc"] = "desc",
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

        if slot_not_null:
            query = query.filter(Save.slot.is_not(None))

        if order_by:
            order_col = getattr(Save, order_by)
            order_fn = asc if order_dir == "asc" else desc
            query = query.order_by(order_fn(order_col))

        if only_fields:
            query = query.options(load_only(*only_fields))

        return session.scalars(query).all()

    @begin_session
    def get_save_by_id(
        self,
        id: int,
        session: Session = None,  # type: ignore
    ) -> Save | None:
        """Fetch a save by id without scoping to an owner. Used for the
        visibility toggle and community downloads, where the caller may not own
        the save. Mirrors db_screenshot_handler.get_screenshot_by_id."""
        return session.get(Save, id)

    @begin_session
    def get_rom_shared_saves(
        self,
        rom_id: int,
        user_id: int,
        public_only: bool = False,
        session: Session = None,  # type: ignore
    ) -> Sequence[Save]:
        """Saves for a ROM visible to the requesting user: own (public +
        private) plus other users' public ones. Mirrors
        db_screenshot_handler.get_rom_gallery_screenshots."""
        query = select(Save).filter(Save.rom_id == rom_id)

        if public_only:
            query = query.filter(Save.is_public)
        else:
            query = query.filter(or_(Save.user_id == user_id, Save.is_public))

        query = query.order_by(desc(Save.updated_at))
        return session.scalars(query).all()

    @begin_session
    def get_latest_saves_for_roms(
        self,
        user_id: int,
        rom_ids: Sequence[int],
        session: Session = None,  # type: ignore
    ) -> dict[int, Save]:
        """The most recent save per ROM for a user, keyed by `rom_id`.

        Batched for the continue-playing rail, which enriches each card with
        the in-game screenshot captured alongside the user's latest save.
        """
        if not rom_ids:
            return {}

        saves = session.scalars(
            select(Save)
            .filter(Save.user_id == user_id, Save.rom_id.in_(rom_ids))
            .order_by(desc(Save.updated_at))
        ).all()

        latest: dict[int, Save] = {}
        for save in saves:
            # Saves come newest-first, so the first one seen per ROM wins.
            latest.setdefault(save.rom_id, save)
        return latest

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

    @begin_session
    def count_saves_missing_content_hash(
        self,
        session: Session = None,  # type: ignore
    ) -> int:
        """Number of Save rows whose content_hash is NULL. Used at startup to
        decide whether the one-shot recompute task needs to be enqueued."""
        return (
            session.scalar(
                select(func.count(Save.id)).where(Save.content_hash.is_(None))
            )
            or 0
        )

    @begin_session
    def get_saves_after_id(
        self,
        after_id: int,
        limit: int,
        session: Session = None,  # type: ignore
    ) -> Sequence[Save]:
        """Page Save rows by primary key. Returns up to ``limit`` rows with
        ``id > after_id``, ordered by id. Used by the
        recompute_save_content_hashes maintenance task to walk every row in
        bounded-memory batches: streaming via ``yield_per`` is incompatible
        with the per-call session lifetime that ``@begin_session`` enforces,
        so the caller drives pagination with this method instead."""
        return session.scalars(
            select(Save).where(Save.id > after_id).order_by(asc(Save.id)).limit(limit)
        ).all()
