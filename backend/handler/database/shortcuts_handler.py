from collections.abc import Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.shortcut import LaunchMode, Shortcut, ShortcutStatus

from .base_handler import DBBaseHandler


class DBShortcutsHandler(DBBaseHandler):
    @begin_session
    def get_shortcut(
        self,
        shortcut_id: int,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> Shortcut | None:
        return session.scalar(
            select(Shortcut).filter_by(id=shortcut_id, user_id=user_id).limit(1)
        )

    @begin_session
    def get_shortcuts(
        self,
        user_id: int,
        *,
        rom_id: int | None = None,
        device_id: str | None = None,
        statuses: Sequence[ShortcutStatus] | None = None,
        session: Session = None,  # type: ignore
    ) -> Sequence[Shortcut]:
        query = select(Shortcut).filter_by(user_id=user_id)
        if rom_id is not None:
            query = query.filter_by(rom_id=rom_id)
        if device_id is not None:
            query = query.filter_by(device_id=device_id)
        if statuses:
            query = query.filter(Shortcut.status.in_(statuses))
        return session.scalars(query.order_by(Shortcut.id)).all()

    @begin_session
    def upsert_pending_add(
        self,
        user_id: int,
        device_id: str,
        rom_id: int,
        launch_mode: LaunchMode | None,
        session: Session = None,  # type: ignore
    ) -> Shortcut:
        """Queue a rom for a device, resetting any previous outcome.

        The unique constraint on (device_id, rom_id) arbitrates a race: the
        request that loses the insert reloads the winner's row and updates it,
        so concurrent queues of the same game stay idempotent.
        """
        existing = session.scalar(
            select(Shortcut).filter_by(device_id=device_id, rom_id=rom_id).limit(1)
        )
        if existing is None:
            created = Shortcut(
                user_id=user_id,
                device_id=device_id,
                rom_id=rom_id,
                status=ShortcutStatus.PENDING_ADD,
                launch_mode=launch_mode,
            )
            try:
                with session.begin_nested():
                    session.add(created)
                return created
            except IntegrityError:
                existing = session.scalar(
                    select(Shortcut)
                    .filter_by(device_id=device_id, rom_id=rom_id)
                    .limit(1)
                )
                if existing is None:
                    raise
        existing.status = ShortcutStatus.PENDING_ADD
        existing.launch_mode = launch_mode
        existing.error = None
        return existing

    @begin_session
    def mark_pending_remove(
        self,
        shortcut_id: int,
        session: Session = None,  # type: ignore
    ) -> Shortcut | None:
        session.execute(
            update(Shortcut)
            .where(Shortcut.id == shortcut_id)
            .values(status=ShortcutStatus.PENDING_REMOVE, error=None)
            .execution_options(synchronize_session="evaluate")
        )
        return session.scalar(select(Shortcut).filter_by(id=shortcut_id).limit(1))

    @begin_session
    def ack(
        self,
        shortcut_id: int,
        *,
        status: ShortcutStatus,
        steam_app_id: int | None = None,
        error: str | None = None,
        session: Session = None,  # type: ignore
    ) -> Shortcut | None:
        values: dict = {"status": status, "error": error}
        if steam_app_id is not None:
            values["steam_app_id"] = steam_app_id
        # A removal queued while the device was working outranks whatever it
        # reports back; otherwise a late staged/added would strand the game in
        # Steam with nothing left asking for its removal.
        session.execute(
            update(Shortcut)
            .where(
                Shortcut.id == shortcut_id,
                Shortcut.status != ShortcutStatus.PENDING_REMOVE,
            )
            .values(**values)
            .execution_options(synchronize_session="evaluate")
        )
        return session.scalar(select(Shortcut).filter_by(id=shortcut_id).limit(1))

    @begin_session
    def delete_shortcut(
        self,
        shortcut_id: int,
        session: Session = None,  # type: ignore
    ) -> None:
        session.execute(
            delete(Shortcut)
            .where(Shortcut.id == shortcut_id)
            .execution_options(synchronize_session="evaluate")
        )
