from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.deleted_asset import MAX_REMEMBERED_HASHES, DeletedAsset
from utils.datetime import to_utc

from .base_handler import DBBaseHandler


class DBDeletedAssetsHandler(DBBaseHandler):
    def record_deletion(
        self,
        user_id: int,
        rom_id: int,
        slot: str,
        content_hash: str | None,
        deleted_at: datetime,
    ) -> DeletedAsset:
        """Remember a version this slot lost, keeping one row per slot.

        Args:
            user_id: Whose library the slot belongs to.
            rom_id: The ROM whose slot lost a version.
            slot: The slot itself.
            content_hash: What that version held, when the save recorded one.
            deleted_at: When it went.

        Returns:
            The record a negotiation will read.
        """
        # Separate transactions: on MariaDB, locking a missing key and then
        # inserting deadlocks a concurrent deletion, even of another slot.
        record = self._merge(user_id, rom_id, slot, content_hash, deleted_at)
        if record:
            return record
        try:
            return self._insert(user_id, rom_id, slot, content_hash, deleted_at)
        except IntegrityError:
            # A concurrent deletion of the same slot inserted first.
            record = self._merge(user_id, rom_id, slot, content_hash, deleted_at)
            if not record:
                raise
            return record

    @begin_session
    def _insert(
        self,
        user_id: int,
        rom_id: int,
        slot: str,
        content_hash: str | None,
        deleted_at: datetime,
        session: Session = None,  # type: ignore
    ) -> DeletedAsset:
        record = DeletedAsset(
            user_id=user_id,
            rom_id=rom_id,
            slot=slot,
            content_hashes=[content_hash] if content_hash else [],
            deleted_at=deleted_at,
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
        content_hash: str | None,
        deleted_at: datetime,
        session: Session = None,  # type: ignore
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
        hashes = [h for h in record.content_hashes or [] if h != content_hash]
        if content_hash:
            hashes.append(content_hash)
        record.content_hashes = hashes[-MAX_REMEMBERED_HASHES:]
        # Through to_utc: a stored value comes back naive on MariaDB, and
        # comparing that with an aware one raises.
        record.deleted_at = max(to_utc(record.deleted_at), to_utc(deleted_at))
        session.flush()
        return record

    @begin_session
    def get_deletions(
        self,
        user_id: int,
        rom_ids: list[int] | None = None,
        session: Session = None,  # type: ignore
    ) -> Sequence[DeletedAsset]:
        """Every slot this user emptied, optionally scoped to some ROMs."""
        query = select(DeletedAsset).filter_by(user_id=user_id)
        if rom_ids is not None:
            if not rom_ids:
                return []
            query = query.filter(DeletedAsset.rom_id.in_(rom_ids))
        return session.scalars(query).all()
