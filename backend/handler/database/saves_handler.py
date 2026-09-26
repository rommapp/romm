from collections.abc import Collection, Sequence
from typing import Literal, Protocol

from sqlalchemy import Select, and_, asc, delete, desc, func, or_, select, update
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.assets import Save
from models.base import with_file_name_parts
from models.rom import Rom

from .base_handler import DBBaseHandler
from .deleted_assets_handler import DBDeletedAssetsHandler

_deleted_assets = DBDeletedAssetsHandler()


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
    def _slot_version(
        self,
        id: int,
        session: Session = None,  # type: ignore
    ) -> Row | None:
        return session.execute(
            select(Save.user_id, Save.rom_id, Save.slot, Save.content_hash).where(
                Save.id == id
            )
        ).one_or_none()

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
        data = with_file_name_parts(data)
        if "content_hash" in data or "slot" in data:
            before = self._slot_version(id)
            if before and (
                data.get("slot", before.slot) != before.slot
                or data.get("content_hash", before.content_hash) != before.content_hash
            ):
                _record_loss(before)
        values = data if touch else {**data, "updated_at": Save.updated_at}
        session.execute(
            update(Save)
            .where(Save.id == id)
            .values(**values)
            .execution_options(synchronize_session="evaluate")
        )
        return session.query(Save).filter_by(id=id).one()

    def prune_slot(
        self,
        user_id: int,
        rom_id: int,
        slot: str,
        keep: int,
    ) -> list[tuple[str, str, str]]:
        """Delete every version of a slot past the ``keep`` newest.

        The rows are locked while they are listed and deleted, so two uploads
        pruning the same slot cannot both keep a version the other dropped.

        Returns:
            ``(file_path, file_name, file_name_no_ext)`` of each deleted version.
        """
        expected = self._versions_past(user_id, rom_id, slot, keep)
        for version in expected:
            _record_loss(version)
        pruned = self._prune(user_id, rom_id, slot, keep)
        # A concurrent upload can push another version past `keep` in between.
        expected_ids = {version.id for version in expected}
        for version in pruned:
            if version.id not in expected_ids:
                _record_loss(version)
        return [(row.file_path, row.file_name, row.file_name_no_ext) for row in pruned]

    @staticmethod
    def _past_keep(user_id: int, rom_id: int, slot: str, keep: int) -> Select:
        return (
            select(
                Save.id,
                Save.user_id,
                Save.rom_id,
                Save.slot,
                Save.content_hash,
                Save.file_path,
                Save.file_name,
                Save.file_name_no_ext,
            )
            .filter_by(user_id=user_id, rom_id=rom_id, slot=slot)
            .order_by(desc(Save.updated_at), desc(Save.id))
            .offset(keep)
        )

    @begin_session
    def _versions_past(
        self,
        user_id: int,
        rom_id: int,
        slot: str,
        keep: int,
        session: Session = None,  # type: ignore
    ) -> Sequence[Row]:
        return session.execute(self._past_keep(user_id, rom_id, slot, keep)).all()

    @begin_session
    def _prune(
        self,
        user_id: int,
        rom_id: int,
        slot: str,
        keep: int,
        session: Session = None,  # type: ignore
    ) -> Sequence[Row]:
        rows = session.execute(
            self._past_keep(user_id, rom_id, slot, keep).with_for_update()
        ).all()
        if rows:
            session.execute(
                delete(Save)
                .where(Save.id.in_([row.id for row in rows]))
                .execution_options(synchronize_session="evaluate")
            )
        return rows

    @begin_session
    def delete_save(
        self,
        id: int,
        content_hash: str | None = None,
        session: Session = None,  # type: ignore
    ) -> None:
        """Delete a save, recording the version its slot loses.

        Args:
            content_hash: What the version held, for a row that never hashed it.
        """
        version = self._slot_version(id)
        if version:
            _record_loss(version, content_hash)
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


class _SlotVersion(Protocol):
    user_id: int
    rom_id: int
    slot: str | None
    content_hash: str | None


def _record_loss(version: _SlotVersion, content_hash: str | None = None) -> None:
    """Remember a version leaving its slot, so a device still holding it is told."""
    # Runs before the row changes and before the caller's session holds a
    # connection, since recording checks out one of its own.
    content_hash = version.content_hash or content_hash
    if version.slot and content_hash:
        _deleted_assets.record_deletion(
            user_id=version.user_id,
            rom_id=version.rom_id,
            slot=version.slot,
            content_hash=content_hash,
        )
