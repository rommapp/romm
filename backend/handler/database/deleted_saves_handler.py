from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.deleted_save import DeletedSave

from .base_handler import DBBaseHandler


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
        """Remember that this slot was emptied, replacing any earlier record.

        Args:
            user_id: Whose library the slot belongs to.
            rom_id: The ROM whose slot was emptied.
            slot: The slot itself.
            content_hash: What it held, when the save recorded one.
            deleted_at: When it was emptied.

        Returns:
            The record a negotiation will read.
        """
        session.execute(
            delete(DeletedSave).where(
                DeletedSave.user_id == user_id,
                DeletedSave.rom_id == rom_id,
                DeletedSave.slot == slot,
            )
        )
        record = DeletedSave(
            user_id=user_id,
            rom_id=rom_id,
            slot=slot,
            content_hash=content_hash,
            deleted_at=deleted_at,
        )
        session.add(record)
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
