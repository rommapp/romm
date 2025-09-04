from collections.abc import Sequence
from functools import partial

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session
from sqlalchemy.sql import Delete, Select, Update

from decorators.database import begin_session
from models.assets import Screenshot

from .base_handler import DBBaseHandler


class DBScreenshotsHandler(DBBaseHandler):
    def filter[QueryT: Select[tuple[Screenshot]] | Update | Delete](
        self,
        query: QueryT,
        *,
        filenames: Sequence[str] = (),
        filenames_no_ext: Sequence[str] = (),
        rom_ids: Sequence[int] = (),
        user_ids: Sequence[int] = (),
        exclude_filenames: Sequence[str] = (),
        exclude_filenames_no_ext: Sequence[str] = (),
    ) -> QueryT:
        if filenames:
            query = query.filter(Screenshot.file_name.in_(filenames))
        if filenames_no_ext:
            query = query.filter(Screenshot.file_name_no_ext.in_(filenames_no_ext))
        if rom_ids:
            query = query.filter(Screenshot.rom_id.in_(rom_ids))
        if user_ids:
            query = query.filter(Screenshot.user_id.in_(user_ids))
        if exclude_filenames:
            query = query.filter(Screenshot.file_name.not_in(exclude_filenames))
        if exclude_filenames_no_ext:
            query = query.filter(
                Screenshot.file_name_no_ext.not_in(exclude_filenames_no_ext)
            )
        return query

    @begin_session
    def add_screenshot(
        self, screenshot: Screenshot, session: Session = None
    ) -> Screenshot:
        return session.merge(screenshot)

    @begin_session
    def get_screenshot(
        self,
        *,
        filename: str | None = None,
        filename_no_ext: str | None = None,
        rom_id: int | None = None,
        user_id: int | None = None,
        session: Session = None,
    ) -> Screenshot | None:
        query = self.filter(
            select(Screenshot),
            filenames=[filename] if filename is not None else (),
            filenames_no_ext=[filename_no_ext] if filename_no_ext is not None else (),
            rom_ids=[rom_id] if rom_id is not None else (),
            user_ids=[user_id] if user_id is not None else (),
        )
        return session.scalars(query.limit(1)).first()

    @begin_session
    def get_screenshot_by_id(self, id, session: Session = None) -> Screenshot | None:
        return session.get(Screenshot, id)

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
    def mark_missing_screenshots(
        self,
        rom_id: int,
        user_id: int,
        screenshots_to_keep: list[str],
        session: Session = None,
    ) -> Sequence[Screenshot]:
        query_fn = partial(
            self.filter,
            rom_ids=[rom_id],
            user_ids=[user_id],
            exclude_filenames=screenshots_to_keep,
        )

        missing_screenshots = session.scalars(query_fn(query=select(Screenshot))).all()

        session.execute(
            query_fn(query=update(Screenshot))
            .values(**{"missing_from_fs": True})
            .execution_options(synchronize_session="evaluate")
        )

        return missing_screenshots
