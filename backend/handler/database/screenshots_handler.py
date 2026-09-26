from collections.abc import Collection, Sequence
from functools import partial

import pydash
from sqlalchemy import case, delete, func, or_, select, update
from sqlalchemy.orm import Session
from sqlalchemy.sql import Delete, Select, Update

from decorators.database import begin_session
from models.assets import Save, Screenshot, State
from models.base import with_file_name_parts

from .base_handler import DBBaseHandler


class DBScreenshotsHandler(DBBaseHandler):
    def filter[QueryT: (Select[tuple[Screenshot]], Update, Delete)](
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
        session: Session = None,  # type: ignore[assignment]
    ) -> Screenshot:
        return session.merge(screenshot)

    @begin_session
    def get_screenshots(
        self,
        *,
        user_id: int,
        rom_ids: Collection[int],
        session: Session = None,  # type: ignore[assignment]
    ) -> Sequence[Screenshot]:
        return session.scalars(
            select(Screenshot).filter(
                Screenshot.user_id == user_id, Screenshot.rom_id.in_(rom_ids)
            )
        ).all()

    @begin_session
    def get_screenshot(
        self,
        *,
        rom_id: int,
        user_id: int,
        file_name: str,
        file_name_no_ext: str | None = None,
        session: Session = None,  # type: ignore[assignment]
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
        id: int,
        session: Session = None,  # type: ignore[assignment]
    ) -> Screenshot | None:
        return session.get(Screenshot, id)

    @begin_session
    def is_bound(
        self,
        screenshot: Screenshot,
        ignoring: Save | State | None = None,
        session: Session = None,  # type: ignore[assignment]
    ) -> bool:
        """Whether a save or state other than `ignoring` shows the screenshot
        as its thumbnail."""
        names = pydash.compact([screenshot.file_name, screenshot.file_name_no_ext])
        for model in (Save, State):
            query = select(model.file_name, model.file_name_no_ext).filter(
                model.rom_id == screenshot.rom_id,
                model.user_id == screenshot.user_id,
                or_(model.file_name.in_(names), model.file_name_no_ext.in_(names)),
            )
            if isinstance(ignoring, model):
                query = query.filter(model.id != ignoring.id)
            # A name can match several screenshots, and the asset shows only
            # the one its lookup prefers.
            for file_name, file_name_no_ext in session.execute(query):
                shown = self.get_screenshot(
                    rom_id=screenshot.rom_id,
                    user_id=screenshot.user_id,
                    file_name=file_name,
                    file_name_no_ext=file_name_no_ext,
                    session=session,
                )
                if shown is not None and shown.id == screenshot.id:
                    return True
        return False

    @begin_session
    def get_name_variants(
        self,
        screenshot: Screenshot,
        session: Session = None,  # type: ignore[assignment]
    ) -> Sequence[Screenshot]:
        """Other screenshots in the same folder whose name differs only in case."""
        query = self.filter(
            select(Screenshot), rom_id=screenshot.rom_id, user_id=screenshot.user_id
        ).filter(
            Screenshot.id != screenshot.id,
            Screenshot.file_path == screenshot.file_path,
            func.lower(Screenshot.file_name) == screenshot.file_name.lower(),
        )
        return session.scalars(query).all()

    @begin_session
    def get_rom_gallery_screenshots(
        self,
        rom_id: int,
        user_id: int,
        public_only: bool = False,
        session: Session = None,  # type: ignore[assignment]
    ) -> Sequence[Screenshot]:
        """Gallery (intentionally-uploaded) screenshots for a ROM, visible to
        the requesting user. Mirrors `db_rom_handler.get_rom_notes`: own
        screenshots (public + private) plus other users' public ones. Excludes
        the auto-captured save/state thumbnails (`is_gallery == False`)."""
        query = select(Screenshot).filter(
            Screenshot.rom_id == rom_id,
            Screenshot.is_gallery,
        )

        if public_only:
            query = query.filter(Screenshot.is_public)
        else:
            query = query.filter(
                or_(Screenshot.user_id == user_id, Screenshot.is_public)
            )

        query = query.order_by(Screenshot.created_at.desc())
        return session.scalars(query).all()

    @begin_session
    def update_screenshot(
        self,
        id: int,
        data: dict,
        session: Session = None,  # type: ignore[assignment]
    ) -> Screenshot:
        session.execute(
            update(Screenshot)
            .where(Screenshot.id == id)
            .values(**with_file_name_parts(data))
            .execution_options(synchronize_session="evaluate")
        )
        return session.scalars(select(Screenshot).filter_by(id=id)).one()

    @begin_session
    def delete_screenshot(
        self,
        id: int,
        session: Session = None,  # type: ignore[assignment]
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
        session: Session = None,  # type: ignore[assignment]
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
