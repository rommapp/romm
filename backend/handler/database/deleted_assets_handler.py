from collections.abc import Collection, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.deleted_asset import MAX_REMEMBERED_HASHES, DeletedAsset

from .base_handler import DBBaseHandler


class DBDeletedAssetsHandler(DBBaseHandler):
    def record_deletion(
        self,
        user_id: int,
        rom_id: int,
        slot: str,
        content_hash: str,
    ) -> DeletedAsset:
        """Remember a version this slot lost, keeping one row per slot.

        Args:
            user_id: Whose library the slot belongs to.
            rom_id: The ROM whose slot lost a version.
            slot: The slot itself.
            content_hash: What that version held.

        Returns:
            The record a negotiation will read.
        """
        # Separate transactions: on MariaDB, locking a missing key and then
        # inserting deadlocks a concurrent deletion, even of another slot.
        record = self._merge(user_id, rom_id, slot, content_hash)
        if record:
            return record
        try:
            return self._insert(user_id, rom_id, slot, content_hash)
        except IntegrityError:
            # A concurrent deletion of the same slot inserted first.
            record = self._merge(user_id, rom_id, slot, content_hash)
            if not record:
                raise
            return record

    @begin_session
    def _insert(
        self,
        user_id: int,
        rom_id: int,
        slot: str,
        content_hash: str,
        session: Session = None,  # type: ignore[assignment]
    ) -> DeletedAsset:
        record = DeletedAsset(
            user_id=user_id,
            rom_id=rom_id,
            slot=slot,
            content_hashes=[content_hash],
        )
        session.add(record)
        session.flush()
        return record

    @begin_session
    def _merge(
        self,
        user_id: int,
        rom_id: int,
        slot: str,
        content_hash: str,
        session: Session = None,  # type: ignore[assignment]
    ) -> DeletedAsset | None:
        """Add this version to the slot's record, or None when it has none yet."""
        record = session.scalar(
            select(DeletedAsset)
            .filter_by(user_id=user_id, rom_id=rom_id, slot=slot)
            .with_for_update()
        )
        if not record:
            return None
        # A version lost again moves to the end, so trimming keeps it.
        hashes = [h for h in record.content_hashes if h != content_hash]
        hashes.append(content_hash)
        record.content_hashes = hashes[-MAX_REMEMBERED_HASHES:]
        session.flush()
        return record

    @begin_session
    def get_deletions(
        self,
        user_id: int,
        rom_ids: Collection[int],
        session: Session = None,  # type: ignore[assignment]
    ) -> Sequence[DeletedAsset]:
        """Every slot of these ROMs this user emptied."""
        if not rom_ids:
            return []
        return session.scalars(
            select(DeletedAsset)
            .filter_by(user_id=user_id)
            .filter(DeletedAsset.rom_id.in_(rom_ids))
        ).all()
