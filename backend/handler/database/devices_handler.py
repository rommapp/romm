from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.device import Device, SyncMode

from .base_handler import DBBaseHandler


class DBDevicesHandler(DBBaseHandler):
    @begin_session
    def add_device(
        self,
        device: Device,
        session: Session = None,  # type: ignore
    ) -> Device:
        return session.merge(device)

    @begin_session
    def get_device(
        self,
        device_id: str,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> Device | None:
        return session.scalar(
            select(Device).filter_by(id=device_id, user_id=user_id).limit(1)
        )

    @begin_session
    def get_device_by_fingerprint(
        self,
        user_id: int,
        mac_address: str | None = None,
        hostname: str | None = None,
        ip_address: str | None = None,
        platform: str | None = None,
        session: Session = None,  # type: ignore
    ) -> Device | None:
        if mac_address:
            device = session.scalar(
                select(Device)
                .filter_by(user_id=user_id, mac_address=mac_address)
                .limit(1)
            )
            if device:
                return device

        if ip_address and platform:
            return session.scalar(
                select(Device)
                .filter_by(user_id=user_id, ip_address=ip_address, platform=platform)
                .limit(1)
            )

        if hostname and platform:
            return session.scalar(
                select(Device)
                .filter_by(user_id=user_id, hostname=hostname, platform=platform)
                .limit(1)
            )

        return None

    @begin_session
    def get_device_by_id(
        self,
        device_id: str,
        session: Session = None,  # type: ignore
    ) -> Device | None:
        """Get a device by ID without user filtering (for server-side operations)."""
        return session.scalar(select(Device).filter_by(id=device_id).limit(1))

    @begin_session
    def get_devices(
        self,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> Sequence[Device]:
        return session.scalars(select(Device).filter_by(user_id=user_id)).all()

    @begin_session
    def get_all_devices_by_sync_mode(
        self,
        sync_mode: SyncMode,
        session: Session = None,  # type: ignore
    ) -> Sequence[Device]:
        """Get all devices with a specific sync mode (across all users)."""
        return session.scalars(select(Device).filter_by(sync_mode=sync_mode)).all()

    @begin_session
    def update_device(
        self,
        device_id: str,
        user_id: int,
        data: dict,
        session: Session = None,  # type: ignore
    ) -> Device | None:
        session.execute(
            update(Device)
            .where(Device.id == device_id, Device.user_id == user_id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )
        return session.scalar(
            select(Device).filter_by(id=device_id, user_id=user_id).limit(1)
        )

    @begin_session
    def update_last_seen(
        self,
        device_id: str,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> None:
        session.execute(
            update(Device)
            .where(Device.id == device_id, Device.user_id == user_id)
            .values(last_seen=datetime.now(timezone.utc))
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def delete_device(
        self,
        device_id: str,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> None:
        session.execute(
            delete(Device)
            .where(Device.id == device_id, Device.user_id == user_id)
            .execution_options(synchronize_session="evaluate")
        )
