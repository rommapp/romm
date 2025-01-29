from typing import Sequence

from decorators.database import begin_session
from models.assets import Screenshot
from sqlalchemy import and_, delete, select, update
from sqlalchemy.orm import Session

from .base_handler import DBBaseHandler


class DBScreenshotsHandler(DBBaseHandler):
    @begin_session
    def add_screenshot(
        self, screenshot: Screenshot, session: Session = None
    ) -> Screenshot:
        return session.merge(screenshot)

    @begin_session
    def get_screenshot(self, id, session: Session = None) -> Screenshot | None:
        return session.get(Screenshot, id)

    @begin_session
    def get_screenshot_by_filename(
        self, rom_id: int, user_id: int, file_name: str, session: Session = None
    ) -> Screenshot | None:
        return session.scalars(
            select(Screenshot)
            .filter_by(rom_id=rom_id, user_id=user_id, file_name=file_name)
            .limit(1)
        ).first()

    @begin_session
    def update_screenshot(
        self, id: int, data: dict, session: Session = None
    ) -> Screenshot:
        session.execute(
            update(Screenshot)
            .where(Screenshot.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )
        return session.query(Screenshot).filter_by(id=id).one()

    @begin_session
    def delete_screenshot(self, id: int, session: Session = None) -> None:
        session.execute(
            delete(Screenshot)
            .where(Screenshot.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def purge_screenshots(
        self,
        rom_id: int,
        user_id: int,
        screenshots_to_keep: list[str],
        session: Session = None,
    ) -> Sequence[Screenshot]:
        purged_screenshots = session.scalars(
            select(Screenshot).filter(
                and_(
                    Screenshot.rom_id == rom_id,
                    Screenshot.user_id == user_id,
                    Screenshot.file_name.not_in(screenshots_to_keep),
                )
            )
        ).all()

        session.execute(
            delete(Screenshot)
            .where(
                and_(
                    Screenshot.rom_id == rom_id,
                    Screenshot.user_id == user_id,
                    Screenshot.file_name.not_in(screenshots_to_keep),
                )
            )
            .execution_options(synchronize_session="evaluate")
        )

        return purged_screenshots
