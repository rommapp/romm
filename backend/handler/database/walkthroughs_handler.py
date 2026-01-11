from typing import Sequence

from sqlalchemy import select

from decorators.database import begin_session
from handler.database.base_handler import DBBaseHandler
from models.walkthrough import Walkthrough


class DBWalkthroughsHandler(DBBaseHandler):
    @begin_session
    def add_or_update_walkthrough(
        self,
        walkthrough: Walkthrough,
        *,
        session=None,  # type: ignore
    ) -> Walkthrough:
        # Use merge to handle both insert and update operations efficiently
        merged_walkthrough = session.merge(walkthrough)
        session.flush()
        session.refresh(merged_walkthrough)  # Ensure we have the latest state
        return merged_walkthrough

    @begin_session
    def get_walkthroughs_for_rom(
        self,
        rom_id: int,
        *,
        session=None,  # type: ignore
    ) -> Sequence[Walkthrough]:
        return session.scalars(
            select(Walkthrough).where(Walkthrough.rom_id == rom_id)
        ).all()

    @begin_session
    def delete_walkthrough(
        self,
        walkthrough_id: int,
        *,
        session=None,  # type: ignore
    ) -> bool:
        walkthrough = session.get(Walkthrough, walkthrough_id)
        if not walkthrough:
            return False
        session.delete(walkthrough)
        session.flush()
        return True

    @begin_session
    def get_walkthrough(
        self,
        walkthrough_id: int,
        *,
        session=None,  # type: ignore
    ) -> Walkthrough | None:
        return session.get(Walkthrough, walkthrough_id)
