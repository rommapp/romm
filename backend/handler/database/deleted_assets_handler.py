from collections.abc import Collection, Sequence
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.deleted_asset import MAX_REMEMBERED_HASHES, DeletedAsset

from .base_handler import DBBaseHandler


class DBDeletedAssetsHandler(DBBaseHandler):
    def ensure_record(self, user_id: int, rom_id: int, slot: str) -> None:
        """Create the slot's empty record if it has none, in its own transaction."""
        # Recording then only locks a row that exists: on MariaDB, locking a
        # missing key and then inserting deadlocks a concurrent deletion.
        if self._exists(user_id, rom_id, slot):
            return
        try:
            self._insert(user_id, rom_id, slot)
        except IntegrityError:
            pass  # A concurrent deletion of the same slot inserted first.

    @begin_session
    def _exists(
        self,
        user_id: int,
        rom_id: int,
        slot: str,
        session: Session = None,  # type: ignore[assignment]
    ) -> bool:
        return (
            session.scalar(
                select(DeletedAsset.id).filter_by(
                    user_id=user_id, rom_id=rom_id, slot=slot
                )
            )
            is not None
        )

    def record_deletion(
        self,
        user_id: int,
        rom_id: int,
        slot: str,
        content_hash: str,
        session: Session | None = None,
    ) -> DeletedAsset:
        """Remember one version this slot lost, as `record_deletions` does."""
        return self.record_deletions(
            user_id, rom_id, slot, [content_hash], session=session
        )

    def record_deletions(
        self,
        user_id: int,
        rom_id: int,
        slot: str,
        content_hashes: Sequence[str],
        session: Session | None = None,
    ) -> DeletedAsset:
        """Remember versions this slot lost, oldest first, keeping one row per slot.

        Args:
            user_id: Whose library the slot belongs to.
            rom_id: The ROM whose slot lost the versions.
            slot: The slot itself.
            content_hashes: What those versions held, oldest first.
            session: The transaction losing the versions, so both commit
                together. Its caller runs `ensure_record` before taking locks.

        Returns:
            The record a negotiation will read.
        """
        if session is None:
            self.ensure_record(user_id, rom_id, slot)
            return self._append(user_id, rom_id, slot, content_hashes)
        return self._append(user_id, rom_id, slot, content_hashes, session=session)

    @begin_session
    def _append(
        self,
        user_id: int,
        rom_id: int,
        slot: str,
        content_hashes: Sequence[str],
        session: Session = None,  # type: ignore[assignment]
    ) -> DeletedAsset:
        record = self.lock_record(user_id, rom_id, slot, session)
        if record is None:
            # The slot changed since its record was ensured, or it was never ensured.
            try:
                with session.begin_nested():
                    record = self._insert(user_id, rom_id, slot, session=session)
            except IntegrityError:
                # A concurrent deletion of the same slot inserted first.
                record = self.lock_record(user_id, rom_id, slot, session)
                if record is None:
                    raise
        # A version lost again moves to the end, so trimming keeps it.
        lost = dict.fromkeys(content_hashes)
        hashes = [h for h in record.content_hashes if h not in lost] + list(lost)
        hashes = hashes[-MAX_REMEMBERED_HASHES:]
        now = datetime.now(timezone.utc).isoformat()
        stamped = record.removed_at or {}
        record.content_hashes = hashes
        record.removed_at = {
            h: now if h in lost else stamped[h]
            for h in hashes
            if h in lost or h in stamped
        }
        session.flush()
        return record

    @begin_session
    def _insert(
        self,
        user_id: int,
        rom_id: int,
        slot: str,
        session: Session = None,  # type: ignore[assignment]
    ) -> DeletedAsset:
        record = DeletedAsset(
            user_id=user_id, rom_id=rom_id, slot=slot, content_hashes=[], removed_at={}
        )
        session.add(record)
        session.flush()
        return record

    @staticmethod
    def lock_record(
        user_id: int, rom_id: int, slot: str, session: Session
    ) -> DeletedAsset | None:
        """Lock the slot's record, which serializes every change to the slot's versions."""
        return session.scalar(
            select(DeletedAsset)
            .filter_by(user_id=user_id, rom_id=rom_id, slot=slot)
            .with_for_update()
        )

    @begin_session
    def removal_times(
        self,
        user_id: int,
        rom_id: int,
        slot: str | None,
        session: Session = None,  # type: ignore[assignment]
    ) -> dict[str, datetime]:
        """When each version this slot lost was lost, empty for a slot that lost none."""
        record = session.scalar(
            select(DeletedAsset).filter_by(user_id=user_id, rom_id=rom_id, slot=slot)
        )
        return record.removal_times() if record else {}

    @begin_session
    def get_deletions(
        self,
        user_id: int,
        rom_ids: Collection[int],
        session: Session = None,  # type: ignore[assignment]
    ) -> Sequence[DeletedAsset]:
        """What each slot of these ROMs lost, for this user."""
        if not rom_ids:
            return []
        return session.scalars(
            select(DeletedAsset)
            .filter_by(user_id=user_id)
            .filter(DeletedAsset.rom_id.in_(rom_ids))
        ).all()
