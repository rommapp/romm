from decorators.database import begin_session
from models.firmware import Firmware
from sqlalchemy import and_, delete, select, update
from sqlalchemy.orm import Session

from .base_handler import DBBaseHandler


class DBFirmwareHandler(DBBaseHandler):
    @begin_session
    def add_firmware(self, firmware: Firmware, session: Session = None) -> Firmware:
        return session.merge(firmware)

    @begin_session
    def get_firmware(
        self,
        id: int,
        *,
        session: Session = None,
    ) -> Firmware | None:
        return session.scalar(select(Firmware).filter_by(id=id).limit(1))

    @begin_session
    def list_firmware(
        self,
        *,
        platform_id: int | None = None,
        session: Session = None,
    ) -> list[Firmware]:
        return session.scalars(
            select(Firmware)
            .filter_by(platform_id=platform_id)
            .order_by(Firmware.file_name.asc())
        ).all()

    @begin_session
    def get_firmware_by_filename(
        self, platform_id: int, file_name: str, session: Session = None
    ):
        return session.scalar(
            select(Firmware)
            .filter_by(platform_id=platform_id, file_name=file_name)
            .limit(1)
        )

    @begin_session
    def update_firmware(self, id: int, data: dict, session: Session = None) -> Firmware:
        return session.execute(
            update(Firmware)
            .where(Firmware.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def delete_firmware(self, id: int, session: Session = None) -> None:
        return session.execute(
            delete(Firmware)
            .where(Firmware.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def purge_firmware(
        self, platform_id: int, fs_firmwares: list[str], session: Session = None
    ) -> None:
        purged_firmware = (
            session.scalars(
                select(Firmware)
                .order_by(Firmware.file_name.asc())
                .where(
                    and_(
                        Firmware.platform_id == platform_id,
                        Firmware.file_name.not_in(fs_firmwares),
                    )
                )
            )  # type: ignore[attr-defined]
            .unique()
            .all()
        )
        session.execute(
            delete(Firmware)
            .where(
                and_(
                    Firmware.platform_id == platform_id,
                    Firmware.file_name.not_in(fs_firmwares),
                )
            )
            .execution_options(synchronize_session="evaluate")
        )
        return purged_firmware
