from collections.abc import Sequence

from sqlalchemy import Select, and_, delete, select, update
from sqlalchemy.orm import Session, noload

from decorators.database import begin_session
from models.firmware import Firmware

from .base_handler import DBBaseHandler


class DBFirmwareHandler(DBBaseHandler):
    @begin_session
    def add_firmware(
        self,
        firmware: Firmware,
        session: Session = None,  # type: ignore
    ) -> Firmware:
        return session.merge(firmware)

    @begin_session
    def get_firmware(
        self,
        id: int,
        *,
        session: Session = None,  # type: ignore
    ) -> Firmware | None:
        return session.scalar(select(Firmware).filter_by(id=id).limit(1))

    def _firmware_query(
        self,
        *,
        platform_ids: Sequence[int] | None = None,
        missing: bool | None = None,
        hidden_platform_ids: Sequence[int] | None = None,
    ) -> Select[tuple[Firmware]]:
        query = select(Firmware).order_by(Firmware.file_name.asc())

        if platform_ids:
            query = query.filter(Firmware.platform_id.in_(platform_ids))

        if missing is not None:
            query = query.filter(Firmware.missing_from_fs == missing)

        # Firmware inherits its platform's visibility: hide firmware whose
        # platform an admin has hidden from the caller.
        if hidden_platform_ids:
            query = query.filter(Firmware.platform_id.not_in(hidden_platform_ids))

        return query

    @begin_session
    def list_firmware(
        self,
        *,
        platform_ids: Sequence[int] | None = None,
        missing: bool | None = None,
        hidden_platform_ids: Sequence[int] | None = None,
        session: Session = None,  # type: ignore
    ) -> Sequence[Firmware]:
        query = self._firmware_query(
            platform_ids=platform_ids,
            missing=missing,
            hidden_platform_ids=hidden_platform_ids,
        )
        # `Firmware.platform` is lazy="joined", which drags in Platform's
        # rom_count and fs_size_bytes subqueries. No caller here reads it.
        return session.scalars(query.options(noload(Firmware.platform))).all()

    @begin_session
    def list_firmware_ids(
        self,
        *,
        platform_ids: Sequence[int] | None = None,
        missing: bool | None = None,
        hidden_platform_ids: Sequence[int] | None = None,
        session: Session = None,  # type: ignore
    ) -> list[int]:
        """Ids only, so no `Firmware` is built and no eager platform join fires."""
        query = self._firmware_query(
            platform_ids=platform_ids,
            missing=missing,
            hidden_platform_ids=hidden_platform_ids,
        )
        return list(session.scalars(query.with_only_columns(Firmware.id)).all())

    @begin_session
    def get_firmware_by_filename(
        self,
        platform_id: int,
        file_name: str,
        session: Session = None,  # type: ignore
    ):
        return session.scalar(
            select(Firmware)
            .filter_by(platform_id=platform_id, file_name=file_name)
            .limit(1)
        )

    @begin_session
    def update_firmware(
        self,
        id: int,
        data: dict,
        session: Session = None,  # type: ignore
    ) -> Firmware:
        session.execute(
            update(Firmware)
            .where(Firmware.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )
        return session.scalars(select(Firmware).filter_by(id=id)).one()

    @begin_session
    def delete_firmware(
        self,
        id: int,
        session: Session = None,  # type: ignore
    ) -> None:
        session.execute(
            delete(Firmware)
            .where(Firmware.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def mark_missing_firmware(
        self,
        platform_id: int,
        fs_firmwares_to_keep: list[str],
        session: Session = None,  # type: ignore
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
            )
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
