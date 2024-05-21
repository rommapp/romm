from decorators.database import begin_session
from models.firmware import Firmware
from sqlalchemy import and_, delete, update
from sqlalchemy.orm import Session

from .base_handler import DBBaseHandler


class DBFirmwareHandler(DBBaseHandler):
    @begin_session
    def add_firmware(self, firmware: Firmware, session: Session = None):
        return session.merge(firmware)

    @begin_session
    def get_firmware(
        self, id: int = None, platform_id: int = None, session: Session = None
    ):
        return (
            session.get(Firmware, id)
            if id
            else session.query(Firmware).filter_by(platform_id=platform_id).all()
        )

    @begin_session
    def get_firmware_by_filename(
        self, platform_id: int, file_name: str, session: Session = None
    ):
        return (
            session.query(Firmware)
            .filter_by(platform_id=platform_id, file_name=file_name)
            .first()
        )

    @begin_session
    def update_firmware(self, id: int, data: dict, session: Session = None):
        return session.execute(
            update(Firmware)
            .where(Firmware.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def delete_firmware(self, id: int, session: Session = None):
        return session.execute(
            delete(Firmware)
            .where(Firmware.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def purge_firmware(
        self, platform_id: int, firmware: list[str], session: Session = None
    ):
        return session.execute(
            delete(Firmware)
            .where(
                and_(
                    Firmware.platform_id == platform_id,
                    Firmware.file_name.not_in(firmware),
                )
            )
            .execution_options(synchronize_session="evaluate")
        )
