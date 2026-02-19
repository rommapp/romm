from collections.abc import Sequence
from functools import partial

import pydash
from sqlalchemy import case, delete, or_, select, update
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
        rom_id: int,
        user_id: int,
        filenames: Sequence[str] = (),
        exclude_filenames: Sequence[str] = (),
    ) -> QueryT:
        query = query.filter(
            Screenshot.rom_id == rom_id,
            Screenshot.user_id == user_id,
        )

        if filenames:
            query = query.filter(
                or_(
                    Screenshot.file_name.in_(filenames),
                    Screenshot.file_name_no_ext.in_(filenames),
                )
            )

        if exclude_filenames:
            query = query.filter(
                Screenshot.file_name.not_in(exclude_filenames),
                Screenshot.file_name_no_ext.not_in(exclude_filenames),
            )

        return query

    @begin_session
    def add_screenshot(
        self,
        screenshot: Screenshot,
        session: Session = None,  # type: ignore
    ) -> Screenshot:
        return session.merge(screenshot)

    @begin_session
    def get_screenshot(
        self,
        *,
        rom_id: int,
        user_id: int,
        file_name: str,
        file_name_no_ext: str | None = None,
        session: Session = None,  # type: ignore
    ) -> Screenshot | None:
        query = self.filter(
            select(Screenshot),
            rom_id=rom_id,
            user_id=user_id,
            filenames=pydash.compact([file_name, file_name_no_ext]),
        )
        # Prefer exact stem matches first
        query = query.order_by(
            case((Screenshot.file_name_no_ext == file_name, 0), else_=1),
            Screenshot.id.desc(),
        )
        return session.scalars(query.limit(1)).first()

    @begin_session
    def get_screenshot_by_id(
        self,
        id,
        session: Session = None,  # type: ignore
    ) -> Screenshot | None:
        return session.get(Screenshot, id)

    @begin_session
    def update_screenshot(
        self,
        id: int,
        data: dict,
        session: Session = None,  # type: ignore
    ) -> Screenshot:
        session.execute(
            update(Screenshot)
            .where(Screenshot.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )
        return session.query(Screenshot).filter_by(id=id).one()

    @begin_session
    def delete_screenshot(
        self,
        id: int,
        session: Session = None,  # type: ignore
    ) -> None:
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
        session: Session = None,  # type: ignore
    ) -> Sequence[Screenshot]:
        query_fn = partial(
            self.filter,
            rom_id=rom_id,
            user_id=user_id,
            exclude_filenames=screenshots_to_keep,
        )

        missing_screenshots = session.scalars(query_fn(query=select(Screenshot))).all()

        session.execute(
            query_fn(query=update(Screenshot))
            .values(**{"missing_from_fs": True})
            .execution_options(synchronize_session="evaluate")
        )

        return missing_screenshots
