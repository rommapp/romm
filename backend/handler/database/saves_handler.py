from collections.abc import Collection, Sequence
from typing import Literal

from sqlalchemy import Select, and_, asc, delete, desc, func, or_, select, update
from sqlalchemy.orm import Session

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
        if slot is not None:
            query = query.filter(Save.slot == slot)
        else:
            query = query.filter(Save.slot.is_(None))
        return session.scalars(query.limit(1)).first()

    @begin_session
    def get_save_by_path(
        self,
        user_id: int,
        rom_id: int,
        file_path: str,
        file_name: str,
        session: Session = None,  # type: ignore
    ) -> Save | None:
        return session.scalars(
            select(Save)
            .filter_by(
                rom_id=rom_id, user_id=user_id, file_path=file_path, file_name=file_name
            )
            .limit(1)
        ).first()

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

    def _saves_query(
        self,
        user_id: int,
        rom_ids: Collection[int] | None = None,
        platform_id: int | None = None,
        slot: str | None = None,
        slot_not_null: bool = False,
        slot_is_null: bool = False,
        file_name_prefix: str | None = None,
        order_by: Literal["updated_at", "created_at"] | None = None,
        order_dir: Literal["asc", "desc"] = "desc",
    ) -> Select[tuple[Save]]:
        query = select(Save).filter_by(user_id=user_id)

        # An empty collection is an explicit empty scope, not an absent filter.
        if rom_ids is not None:
            query = query.filter(Save.rom_id.in_(rom_ids))

        if platform_id:
            query = query.join(Rom, Save.rom_id == Rom.id).filter(
                Rom.platform_id == platform_id
            )

        if slot is not None:
            query = query.filter(Save.slot == slot)

        if slot_not_null:
            query = query.filter(Save.slot.is_not(None))

        if slot_is_null:
            query = query.filter(Save.slot.is_(None))

        if file_name_prefix:
            query = query.filter(
                Save.file_name.startswith(file_name_prefix, autoescape=True)
            )

        if order_by:
            order_col = getattr(Save, order_by)
            order_fn = asc if order_dir == "asc" else desc
            # Timestamps tie at second resolution; the id keeps the order stable.
            query = query.order_by(order_fn(order_col), order_fn(Save.id))

        return query

    @begin_session
    def get_saves(
        self,
        user_id: int,
        rom_ids: Collection[int] | None = None,
        platform_id: int | None = None,
        slot: str | None = None,
        slot_not_null: bool = False,
        slot_is_null: bool = False,
        file_name_prefix: str | None = None,
        order_by: Literal["updated_at", "created_at"] | None = None,
        order_dir: Literal["asc", "desc"] = "desc",
        session: Session = None,  # type: ignore
    ) -> Sequence[Save]:
        query = self._saves_query(
            user_id=user_id,
            rom_ids=rom_ids,
            platform_id=platform_id,
            slot=slot,
            slot_not_null=slot_not_null,
            slot_is_null=slot_is_null,
            file_name_prefix=file_name_prefix,
            order_by=order_by,
            order_dir=order_dir,
        )
        return session.scalars(query).all()

    @begin_session
    def get_save_ids(
        self,
        user_id: int,
        rom_ids: Collection[int] | None = None,
        platform_id: int | None = None,
        slot: str | None = None,
        slot_not_null: bool = False,
        order_by: Literal["updated_at", "created_at"] | None = None,
        order_dir: Literal["asc", "desc"] = "desc",
        session: Session = None,  # type: ignore
    ) -> list[int]:
        """Ids only, so no `Save` is built and no eager rom or user join fires."""
        query = self._saves_query(
            user_id=user_id,
            rom_ids=rom_ids,
            platform_id=platform_id,
            slot=slot,
            slot_not_null=slot_not_null,
            order_by=order_by,
            order_dir=order_dir,
        )
        return list(session.scalars(query.with_only_columns(Save.id)).all())

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
        touch: bool = True,
        session: Session = None,  # type: ignore
    ) -> Save:
        """Write `data` onto a save.

        Args:
            touch: False keeps `updated_at`, since annotating is not a write
                to the bytes and device sync reads it to detect staleness.
        """
        values = data if touch else {**data, "updated_at": Save.updated_at}
        session.execute(
            update(Save)
            .where(Save.id == id)
            .values(**values)
            .execution_options(synchronize_session="evaluate")
        )
        return session.query(Save).filter_by(id=id).one()

    @begin_session
    def prune_slot(
        self,
        user_id: int,
        rom_id: int,
        slot: str,
        keep: int,
        session: Session = None,  # type: ignore
    ) -> list[tuple[str, str, str]]:
        """Delete every version of a slot past the ``keep`` newest.

        The rows are locked while they are listed and deleted, so two uploads
        pruning the same slot cannot both keep a version the other dropped.

        Returns:
            ``(file_path, file_name, file_name_no_ext)`` of each deleted version.
        """
        rows = session.execute(
            select(Save.id, Save.file_path, Save.file_name, Save.file_name_no_ext)
            .filter_by(user_id=user_id, rom_id=rom_id, slot=slot)
            .order_by(desc(Save.updated_at), desc(Save.id))
            .offset(keep)
            .with_for_update()
        ).all()
        if rows:
            session.execute(
                delete(Save)
                .where(Save.id.in_([row.id for row in rows]))
                .execution_options(synchronize_session="evaluate")
            )
        return [(row.file_path, row.file_name, row.file_name_no_ext) for row in rows]

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
