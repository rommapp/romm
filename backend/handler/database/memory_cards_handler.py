from collections.abc import Sequence

from sqlalchemy import delete, desc, or_, select, update
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.assets import MemoryCard, MemoryCardVersion

from .base_handler import DBBaseHandler


class DBMemoryCardsHandler(DBBaseHandler):
    # --- Card identity ---

    @begin_session
    def add_card(
        self,
        card: MemoryCard,
        session: Session = None,  # type: ignore
    ) -> MemoryCard:
        return session.merge(card)

    @begin_session
    def get_card(
        self,
        user_id: int,
        id: int,
        session: Session = None,  # type: ignore
    ) -> MemoryCard | None:
        """Owner-scoped fetch, for mutations the caller must own (rename,
        share, delete)."""
        return session.scalar(
            select(MemoryCard).filter_by(user_id=user_id, id=id).limit(1)
        )

    @begin_session
    def get_card_by_id(
        self,
        id: int,
        session: Session = None,  # type: ignore
    ) -> MemoryCard | None:
        """Unscoped fetch. Used when hydrating a card shared by another user,
        where the caller does not own it (visibility is enforced separately)."""
        return session.get(MemoryCard, id)

    @begin_session
    def get_cards(
        self,
        user_id: int,
        emulator: str | None = None,
        session: Session = None,  # type: ignore
    ) -> Sequence[MemoryCard]:
        """A user's own cards, optionally filtered to one emulator (the pick
        list shown at session claim)."""
        query = select(MemoryCard).filter_by(user_id=user_id)
        if emulator is not None:
            query = query.filter(MemoryCard.emulator == emulator)
        return session.scalars(query.order_by(desc(MemoryCard.updated_at))).all()

    @begin_session
    def get_shared_cards(
        self,
        emulator: str,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> Sequence[MemoryCard]:
        """Cards for an emulator visible to the requesting user: their own plus
        other users' public ones. Mirrors db_state_handler.get_rom_shared_states
        but keyed by emulator rather than rom."""
        query = (
            select(MemoryCard)
            .filter(MemoryCard.emulator == emulator)
            .filter(or_(MemoryCard.user_id == user_id, MemoryCard.is_public))
            .order_by(desc(MemoryCard.updated_at))
        )
        return session.scalars(query).all()

    @begin_session
    def update_card(
        self,
        id: int,
        data: dict,
        session: Session = None,  # type: ignore
    ) -> MemoryCard:
        session.execute(
            update(MemoryCard)
            .where(MemoryCard.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )
        return session.query(MemoryCard).filter_by(id=id).one()

    @begin_session
    def delete_card(
        self,
        id: int,
        session: Session = None,  # type: ignore
    ) -> None:
        # Versions cascade via the FK / relationship.
        session.execute(
            delete(MemoryCard)
            .where(MemoryCard.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    # --- Card versions (snapshots) ---

    @begin_session
    def add_version(
        self,
        version: MemoryCardVersion,
        session: Session = None,  # type: ignore
    ) -> MemoryCardVersion:
        return session.merge(version)

    @begin_session
    def get_latest_version(
        self,
        card_id: int,
        session: Session = None,  # type: ignore
    ) -> MemoryCardVersion | None:
        """Newest snapshot of a card, used to hydrate a container at claim."""
        return session.scalar(
            select(MemoryCardVersion)
            .filter_by(memory_card_id=card_id)
            .order_by(desc(MemoryCardVersion.created_at))
            .limit(1)
        )

    @begin_session
    def get_version_by_content_hash(
        self,
        card_id: int,
        content_hash: str,
        session: Session = None,  # type: ignore
    ) -> MemoryCardVersion | None:
        """Dedup lookup on evacuate: skip storing a snapshot identical to one
        already held for this card."""
        return session.scalar(
            select(MemoryCardVersion)
            .filter_by(memory_card_id=card_id, content_hash=content_hash)
            .limit(1)
        )

    @begin_session
    def get_version_by_id(
        self,
        id: int,
        session: Session = None,  # type: ignore
    ) -> MemoryCardVersion | None:
        """Unscoped fetch, for the content-download route."""
        return session.get(MemoryCardVersion, id)

    @begin_session
    def get_versions(
        self,
        card_id: int,
        session: Session = None,  # type: ignore
    ) -> Sequence[MemoryCardVersion]:
        """A card's snapshot history, newest first."""
        return session.scalars(
            select(MemoryCardVersion)
            .filter_by(memory_card_id=card_id)
            .order_by(desc(MemoryCardVersion.created_at))
        ).all()

    @begin_session
    def delete_version(
        self,
        id: int,
        session: Session = None,  # type: ignore
    ) -> None:
        session.execute(
            delete(MemoryCardVersion)
            .where(MemoryCardVersion.id == id)
            .execution_options(synchronize_session="evaluate")
        )
