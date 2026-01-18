from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.device import Device

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
    def get_devices(
        self,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> Sequence[Device]:
        return session.scalars(select(Device).filter_by(user_id=user_id)).all()

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
