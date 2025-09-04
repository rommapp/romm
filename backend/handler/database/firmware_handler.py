from collections.abc import Sequence

from sqlalchemy import and_, delete, select, update
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.firmware import Firmware

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
    ) -> Sequence[Firmware]:
        query = select(Firmware).order_by(Firmware.file_name.asc())

        if platform_id:
            query = query.filter_by(platform_id=platform_id)

        return session.scalars(query).all()

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
        session.execute(
            update(Firmware)
            .where(Firmware.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )
        return session.query(Firmware).filter_by(id=id).one()

    @begin_session
    def delete_firmware(self, id: int, session: Session = None) -> None:
        session.execute(
            delete(Firmware)
            .where(Firmware.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def mark_missing_firmware(
        self, platform_id: int, fs_firmwares_to_keep: list[str], session: Session = None
    ) -> Sequence[Firmware]:
        missing_firmware = (
            session.scalars(
                select(Firmware)
                .order_by(Firmware.file_name.asc())
                .where(
                    and_(
                        Firmware.platform_id == platform_id,
                        Firmware.file_name.not_in(fs_firmwares_to_keep),
                    )
                )
            )  # type: ignore[attr-defined]
            .unique()
            .all()
        )
        session.execute(
            update(Firmware)
            .where(
                and_(
                    Firmware.platform_id == platform_id,
                    Firmware.file_name.not_in(fs_firmwares_to_keep),
                )
            )
            .values(**{"missing_from_fs": True})
            .execution_options(synchronize_session="evaluate")
        )
        return missing_firmware
