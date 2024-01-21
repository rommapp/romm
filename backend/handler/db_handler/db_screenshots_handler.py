from decorators.database import begin_session
from handler.db_handler import DBHandler
from models.assets import Screenshot
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session


class DBScreenshotsHandler(DBHandler):
    @begin_session
    def add_screenshot(self, screenshot: Screenshot, session: Session = None):
        return session.merge(screenshot)

    @begin_session
    def get_screenshot(self, id, session: Session = None):
        return session.get(Screenshot, id)

    @begin_session
    def get_screenshot_by_filename(
        self, file_name: str, rom_id: str = None, session: Session = None
    ):
        return session.scalars(
            select(Screenshot)
            .filter_by(file_name=file_name)
            .where(Screenshot.rom_id == rom_id if rom_id else True)
            .limit(1)
        ).first()

    @begin_session
    def update_screenshot(self, id: int, data: dict, session: Session = None):
        session.execute(
            update(Screenshot)
            .where(Screenshot.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def delete_screenshot(self, id: int, session: Session = None):
        return session.execute(
            delete(Screenshot)
            .where(Screenshot.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def purge_screenshots(
        self, rom_id: int, screenshots: list[str], session: Session = None
    ):
        return session.execute(
            delete(Screenshot)
            .where(
                Screenshot.rom_id == rom_id,
                Screenshot.file_name.not_in(screenshots),
            )
            .execution_options(synchronize_session="evaluate")
        )
