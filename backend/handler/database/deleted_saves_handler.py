from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.deleted_save import DeletedSave
from utils.datetime import to_utc

from .base_handler import DBBaseHandler

# Versions remembered per slot, read on every negotiation that finds the slot
# empty. Trimming drops the oldest, which are the ones a long-offline device is
# likeliest to still hold, so the bound is set where that device would have had
# to miss a hundred delete-and-refill cycles of one slot. Past it the slot's
# deletion is simply not known for those bytes and the device is answered
# `upload`, which is the direction that cannot lose a save.
MAX_REMEMBERED_HASHES = 100


class DBDeletedSavesHandler(DBBaseHandler):
    @begin_session
    def record_deletion(
        self,
        user_id: int,
        rom_id: int,
        slot: str,
        content_hash: str | None,
        deleted_at: datetime,
        session: Session = None,  # type: ignore
    ) -> DeletedSave:
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
        existing = self._locked(session, user_id, rom_id, slot)
        if existing:
            return self._merge(existing, content_hash, deleted_at, session)

        record = DeletedSave(
            user_id=user_id,
            rom_id=rom_id,
            slot=slot,
            content_hashes=[content_hash] if content_hash else [],
            deleted_at=deleted_at,
        )
        try:
            # Two deletions of the same slot can each find no row to lock,
            # since there is nothing there to lock yet. The loser merges.
            with session.begin_nested():
                session.add(record)
                session.flush()
        except IntegrityError:
            winner = self._locked(session, user_id, rom_id, slot)
            if not winner:
                raise
            return self._merge(winner, content_hash, deleted_at, session)
        return record

    def _locked(
        self, session: Session, user_id: int, rom_id: int, slot: str
    ) -> DeletedSave | None:
        """This slot's record, held against a concurrent deletion of the same."""
        return session.scalar(
            select(DeletedSave)
            .filter_by(user_id=user_id, rom_id=rom_id, slot=slot)
            .with_for_update()
        )

    def _merge(
        self,
        record: DeletedSave,
        content_hash: str | None,
        deleted_at: datetime,
        session: Session,
    ) -> DeletedSave:
        """Add this version to what the slot is known to have lost."""
        hashes = list(record.content_hashes or [])
        if content_hash and content_hash not in hashes:
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
    ) -> Sequence[DeletedSave]:
        """Every slot this user emptied, optionally scoped to some ROMs."""
        query = select(DeletedSave).filter_by(user_id=user_id)
        if rom_ids is not None:
            if not rom_ids:
                return []
            query = query.filter(DeletedSave.rom_id.in_(rom_ids))
        return session.scalars(query).all()
