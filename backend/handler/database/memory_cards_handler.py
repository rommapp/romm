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
        """Unscoped fetch, for reads that may cross ownership (a public card's
        detail or version list) and for lookups by an id already resolved to
        the session's own card. Visibility is enforced separately by the
        caller; this never scopes by user on its own."""
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
        other users' public ones. Browsing only, since another user's card is
        never mounted onto a session (see _resolve_memory_card). Mirrors
        db_state_handler.get_rom_shared_states but keyed by emulator."""
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
    ) -> MemoryCard | None:
        """Returns None when the row was deleted concurrently."""
        session.execute(
            update(MemoryCard)
            .where(MemoryCard.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )
        return session.query(MemoryCard).filter_by(id=id).one_or_none()

    @begin_session
    def delete_card(
        self,
        id: int,
        session: Session = None,  # type: ignore
    ) -> list[str]:
        """Delete a card and return the paths of the version archives that went
        with it. The listing shares the delete's transaction and locks the rows,
        so a snapshot written alongside cannot end up deleted in the database and
        absent from the caller's removal list."""
        paths = [
            f"{file_path}/{file_name}"
            for file_path, file_name in session.execute(
                select(MemoryCardVersion.file_path, MemoryCardVersion.file_name)
                .filter_by(memory_card_id=id)
                .with_for_update()
            ).all()
        ]

        # Versions cascade via the FK / relationship.
        session.execute(
            delete(MemoryCard)
            .where(MemoryCard.id == id)
            .execution_options(synchronize_session="evaluate")
        )
        return paths

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
        """Newest snapshot of a card, used to hydrate a container at claim.

        Ties on id, because created_at only has second resolution: an upload
        landing in the same second as an evacuated snapshot would otherwise
        hydrate arbitrarily.
        """
        return session.scalar(
            select(MemoryCardVersion)
            .filter_by(memory_card_id=card_id)
            .order_by(desc(MemoryCardVersion.created_at), desc(MemoryCardVersion.id))
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
            .order_by(desc(MemoryCardVersion.created_at), desc(MemoryCardVersion.id))
        ).all()

    @begin_session
    def set_version_missing(
        self,
        id: int,
        missing: bool,
        session: Session = None,  # type: ignore
    ) -> None:
        """Record whether a version's archive is still on disk, so the history
        can say a snapshot is gone instead of offering a download that 404s."""
        session.execute(
            update(MemoryCardVersion)
            .where(MemoryCardVersion.id == id)
            .values(missing_from_fs=missing)
            .execution_options(synchronize_session="evaluate")
        )

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
