from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.device import Device
from models.device_save_sync import DeviceSaveSync

from .base_handler import DBBaseHandler


class DBDeviceSaveSyncHandler(DBBaseHandler):
    @begin_session
    def get_sync(
        self,
        device_id: str,
        save_id: int,
        session: Session = None,  # type: ignore
    ) -> DeviceSaveSync | None:
        return session.scalar(
            select(DeviceSaveSync)
            .filter_by(device_id=device_id, save_id=save_id)
            .limit(1)
        )

    @begin_session
    def get_syncs_for_device_and_saves(
        self,
        device_id: str,
        save_ids: list[int],
        session: Session = None,  # type: ignore
    ) -> Sequence[DeviceSaveSync]:
        if not save_ids:
            return []
        return session.scalars(
            select(DeviceSaveSync).filter(
                DeviceSaveSync.device_id == device_id,
                DeviceSaveSync.save_id.in_(save_ids),
            )
        ).all()

    @begin_session
    def get_syncs_for_saves(
        self,
        save_ids: list[int],
        session: Session = None,  # type: ignore
    ) -> dict[int, list[tuple[DeviceSaveSync, str | None]]]:
        """Fetch every device sync row for the given saves, grouped by save id.

        Each row is paired with its device name so callers can attribute a save
        to the device that created it without triggering the lazy-raise
        ``DeviceSaveSync.device`` relationship.
        """
        if not save_ids:
            return {}
        rows = session.execute(
            select(DeviceSaveSync, Device.name)
            .join(Device, DeviceSaveSync.device_id == Device.id)
            .filter(DeviceSaveSync.save_id.in_(save_ids))
            .order_by(DeviceSaveSync.last_synced_at.desc(), DeviceSaveSync.device_id)
        ).all()
        grouped: dict[int, list[tuple[DeviceSaveSync, str | None]]] = {}
        for sync, device_name in rows:
            grouped.setdefault(sync.save_id, []).append((sync, device_name))
        return grouped

    @begin_session
    def upsert_sync(
        self,
        device_id: str,
        save_id: int,
        synced_at: datetime | None = None,
        session: Session = None,  # type: ignore
    ) -> DeviceSaveSync:
        now = synced_at or datetime.now(timezone.utc)
        existing = session.scalar(
            select(DeviceSaveSync)
            .filter_by(device_id=device_id, save_id=save_id)
            .limit(1)
        )
        if existing:
            session.execute(
                update(DeviceSaveSync)
                .where(
                    DeviceSaveSync.device_id == device_id,
                    DeviceSaveSync.save_id == save_id,
                )
                .values(last_synced_at=now, is_untracked=False)
                .execution_options(synchronize_session="evaluate")
            )
            existing.last_synced_at = now
            existing.is_untracked = False
            return existing
        else:
            sync = DeviceSaveSync(
                device_id=device_id,
                save_id=save_id,
                last_synced_at=now,
                is_untracked=False,
            )
            session.add(sync)
            session.flush()
            return sync

    @begin_session
    def set_untracked(
        self,
        device_id: str,
        save_id: int,
        untracked: bool,
        session: Session = None,  # type: ignore
    ) -> DeviceSaveSync | None:
        existing = session.scalar(
            select(DeviceSaveSync)
            .filter_by(device_id=device_id, save_id=save_id)
            .limit(1)
        )
        if existing:
            session.execute(
                update(DeviceSaveSync)
                .where(
                    DeviceSaveSync.device_id == device_id,
                    DeviceSaveSync.save_id == save_id,
                )
                .values(is_untracked=untracked)
                .execution_options(synchronize_session="evaluate")
            )
            existing.is_untracked = untracked
            return existing
        elif untracked:
            now = datetime.now(timezone.utc)
            sync = DeviceSaveSync(
                device_id=device_id,
                save_id=save_id,
                last_synced_at=now,
                is_untracked=True,
            )
            session.add(sync)
            session.flush()
            return sync
        return None

    @begin_session
    def delete_syncs_for_device(
        self,
        device_id: str,
        session: Session = None,  # type: ignore
    ) -> None:
        session.execute(
            delete(DeviceSaveSync)
            .where(DeviceSaveSync.device_id == device_id)
            .execution_options(synchronize_session="evaluate")
        )
