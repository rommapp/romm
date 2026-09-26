import functools
from collections.abc import Callable, Collection, Mapping, Sequence
from typing import Any, Literal

from sqlalchemy import Select, and_, asc, delete, desc, func, or_, select, update
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.assets import SAVE_SLOT_VERSIONS_INDEX, Save
from models.base import with_file_name_parts
from models.rom import Rom
from utils.sql_dialect import force_index_on_mysql

from .base_handler import DBBaseHandler, affected_rows
from .deleted_assets_handler import DBDeletedAssetsHandler

_deleted_assets = DBDeletedAssetsHandler()
# What identifies a version in its slot, for recording it when it leaves.
_VERSION_COLUMNS = (Save.user_id, Save.rom_id, Save.slot, Save.content_hash)
_SLOT_MOVE_ATTEMPTS = 3


class _SlotMoved(Exception):
    """The save changed slot between the unlocked read and its lock."""


class UnhashedVersions(Exception):
    """Versions a prune would drop without a hash to record them by."""

    def __init__(self, versions: Sequence[Row[Any]]):
        super().__init__(f"{len(versions)} versions to prune were never hashed")
        self.versions = versions


def _retry_if_slot_moved[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Rerun a removal in a fresh transaction, releasing the stale slot's lock."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        if kwargs.get("session") is not None:
            return func(*args, **kwargs)
        for _ in range(_SLOT_MOVE_ATTEMPTS - 1):
            try:
                return func(*args, **kwargs)
            except _SlotMoved:
                continue
        return func(*args, **kwargs)

    return wrapper


class DBSavesHandler(DBBaseHandler):
    @begin_session
    def add_save(
        self,
        save: Save,
        session: Session = None,  # type: ignore[assignment]
    ) -> Save:
        return session.merge(save)

    @begin_session
    def get_save(
        self,
        user_id: int,
        id: int,
        session: Session = None,  # type: ignore[assignment]
    ) -> Save | None:
        return session.scalar(select(Save).filter_by(user_id=user_id, id=id).limit(1))

    @begin_session
    def get_save_by_filename(
        self,
        user_id: int,
        rom_id: int,
        file_name: str,
        slot: str | None = None,
        session: Session = None,  # type: ignore[assignment]
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
        session: Session = None,  # type: ignore[assignment]
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
        session: Session = None,  # type: ignore[assignment]
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
        session: Session = None,  # type: ignore[assignment]
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
        session: Session = None,  # type: ignore[assignment]
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
        session: Session = None,  # type: ignore[assignment]
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
        session: Session = None,  # type: ignore[assignment]
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
        session: Session = None,  # type: ignore[assignment]
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
        session: Session = None,  # type: ignore[assignment]
    ) -> Row[Any] | None:
        return session.execute(_version_query(id)).one_or_none()

    def _lock_for_removal(self, id: int, session: Session) -> Row[Any] | None:
        """Lock the save's slot record, then the save, returning its current version."""
        # Before this session holds a connection, since ensuring takes its own.
        before = self._slot_version(id)
        if not before:
            return None
        if before.slot:
            _lock_slot(before.user_id, before.rom_id, before.slot, session)
        current = session.execute(_version_query(id).with_for_update()).one_or_none()
        # Locking the slot it moved to now would take a slot after a row.
        if current and current.slot and current.slot != before.slot:
            raise _SlotMoved
        return current

    @_retry_if_slot_moved
    @begin_session
    def update_save(
        self,
        id: int,
        data: dict[str, Any],
        touch: bool = True,
        replaced_hash: str | None = None,
        session: Session = None,  # type: ignore[assignment]
    ) -> Save:
        """Write `data` onto a save.

        Args:
            touch: False keeps `updated_at`, since annotating is not a write
                to the bytes and device sync reads it to detect staleness.
            replaced_hash: What the version held, for a row that never hashed it.
        """
        data = with_file_name_parts(data)
        if "content_hash" in data or "slot" in data:
            current = self._lock_for_removal(id, session)
            if current and _loses_version(current, data):
                _record_loss(current, session, replaced_hash)
        return self._write(id, data, touch, session)

    @begin_session
    def rehash_save(
        self,
        id: int,
        content_hash: str,
        replacing: str | None,
        session: Session = None,  # type: ignore[assignment]
    ) -> bool:
        """Store a recomputed hash of the same bytes, so no version leaves the slot.

        Args:
            content_hash: The recomputed hash.
            replacing: The hash it was computed against; a row holding another
                was rewritten meanwhile and keeps its own.

        Returns:
            Whether the row still held ``replacing`` and took the new hash.
        """
        # Keeps `updated_at`, as `touch=False` does: device sync reads it as a write.
        result = session.execute(
            update(Save)
            .where(Save.id == id, Save.content_hash.is_not_distinct_from(replacing))
            .values(content_hash=content_hash, updated_at=Save.updated_at)
            .execution_options(synchronize_session=False)
        )
        return affected_rows(result) == 1

    @staticmethod
    def _write(id: int, data: dict[str, Any], touch: bool, session: Session) -> Save:
        values = data if touch else {**data, "updated_at": Save.updated_at}
        session.execute(
            update(Save)
            .where(Save.id == id)
            .values(**values)
            .execution_options(synchronize_session="evaluate")
        )
        return session.scalars(select(Save).filter_by(id=id)).one()

    @begin_session
    def prune_slot(
        self,
        user_id: int,
        rom_id: int,
        slot: str,
        keep: int,
        fallback_hashes: Mapping[int, str | None] | None = None,
        session: Session = None,  # type: ignore[assignment]
    ) -> Sequence[Row[Any]]:
        """Delete every version of a slot past the ``keep`` newest.

        The slot's record is locked while its versions are listed and deleted,
        so two uploads pruning it cannot both keep a version the other dropped.

        Args:
            fallback_hashes: What versions never hashed held, by save id, or
                None for a file that couldn't be read.

        Returns:
            Each deleted version's hash and ``file_path``, ``file_name`` and
            ``file_name_no_ext``, newest first.

        Raises:
            UnhashedVersions: Deleting nothing, for versions never hashed that
                ``fallback_hashes`` lacks.
        """
        past_keep = (
            select(
                Save.id,
                *_VERSION_COLUMNS,
                Save.file_path,
                Save.file_name,
                Save.file_name_no_ext,
            )
            .filter_by(user_id=user_id, rom_id=rom_id, slot=slot)
            .order_by(desc(Save.updated_at), desc(Save.id))
            .offset(keep)
        )
        # Before this session holds a connection, since ensuring takes its own.
        if not self._any(past_keep):
            return []
        _lock_slot(user_id, rom_id, slot, session)
        # Locks only this slot's rows and takes no snapshot, which MariaDB's
        # snapshot isolation would fail the delete against.
        rows = session.execute(
            force_index_on_mysql(
                past_keep, Save, SAVE_SLOT_VERSIONS_INDEX
            ).with_for_update()
        ).all()
        fallback_hashes = fallback_hashes or {}
        unhashed = [
            row
            for row in rows
            if not row.content_hash and row.id not in fallback_hashes
        ]
        if unhashed:
            raise UnhashedVersions(unhashed)
        # Oldest first, so trimming the record drops the oldest version first.
        lost = [
            content_hash
            for row in reversed(rows)
            if (content_hash := row.content_hash or fallback_hashes.get(row.id))
        ]
        if lost:
            _deleted_assets.record_deletions(
                user_id, rom_id, slot, lost, session=session
            )
        # One row at a time: MariaDB's `id IN (...)` plan deadlocks concurrent prunes.
        for row in rows:
            session.execute(
                delete(Save)
                .where(Save.id == row.id)
                .execution_options(synchronize_session="evaluate")
            )
        return rows

    @begin_session
    def _any(
        self,
        query: Select[Any],
        session: Session = None,  # type: ignore[assignment]
    ) -> bool:
        return session.execute(query.limit(1)).first() is not None

    @_retry_if_slot_moved
    @begin_session
    def delete_save(
        self,
        id: int,
        content_hash: str | None = None,
        session: Session = None,  # type: ignore[assignment]
    ) -> None:
        """Delete a save, recording the version its slot loses.

        Args:
            content_hash: What the version held, for a row that never hashed it.
        """
        current = self._lock_for_removal(id, session)
        if current:
            _record_loss(current, session, content_hash)
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
        session: Session = None,  # type: ignore[assignment]
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
        session: Session = None,  # type: ignore[assignment]
    ) -> dict[str, Any]:
        saves = session.scalars(
            select(Save)
            .filter_by(user_id=user_id, rom_id=rom_id)
            .order_by(desc(Save.updated_at))
        ).all()

        slots_data: dict[str | None, dict[str, Any]] = {}
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
        session: Session = None,  # type: ignore[assignment]
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
        session: Session = None,  # type: ignore[assignment]
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


def _version_query(id: int) -> Select[Any]:
    return select(*_VERSION_COLUMNS).where(Save.id == id)


def _loses_version(version: Row[Any], data: dict[str, Any]) -> bool:
    """Whether writing `data` takes this version out of its slot."""
    return (
        data.get("slot", version.slot) != version.slot
        or data.get("content_hash", version.content_hash) != version.content_hash
    )


def _lock_slot(user_id: int, rom_id: int, slot: str, session: Session) -> None:
    """Ensure the slot has a record, then lock it before any of its rows."""
    # One order everywhere, the record before the rows, so removals never deadlock.
    _deleted_assets.ensure_record(user_id, rom_id, slot)
    _deleted_assets.lock_record(user_id, rom_id, slot, session)


def _record_loss(
    version: Row[Any], session: Session, content_hash: str | None = None
) -> None:
    """Remember a version leaving its slot, in the transaction that removes it."""
    content_hash = version.content_hash or content_hash
    if version.slot and content_hash:
        _deleted_assets.record_deletion(
            version.user_id,
            version.rom_id,
            version.slot,
            content_hash,
            session=session,
        )
