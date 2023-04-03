import functools

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from models.base import Session, BaseModel, engine
from models.platform import Platform
from models.rom import Rom
from logger.logger import log


class DBHandler:   
    def __init__(self) -> None:
        BaseModel.metadata.create_all(engine)
        self.session = Session()


    def retry(func) -> tuple:
        @functools.wraps(func)
        def wrapper(*args):
            return func(*args)
        return wrapper

    
    def add_platform(self, Platform: Platform) -> None:
        try:
            with Session.begin() as session:
                session.merge(Platform)
        except ProgrammingError as e:
            raise HTTPException(status_code=404, detail=f"Platforms table not found: {e}")

    def get_platforms(self) -> list[Platform]:
        try:
            with Session.begin() as session:
                return session.scalars(select(Platform).order_by(Platform.slug.asc())).all()
        except ProgrammingError as e:
            raise HTTPException(status_code=404, detail=f"Platforms table not found: {e}")

    def add_rom(self, rom: Rom) -> None:
        with Session.begin() as session:
            session.merge(rom)

    def get_roms(self, p_slug: str) -> list[Rom]:
        with Session.begin() as session:
            return session.scalars(select(Rom).filter_by(p_slug=p_slug).order_by(Rom.file_name.asc())).all()

    def get_rom(self, p_slug: str, file_name: str) -> Rom:
        with Session.begin() as session:
            return session.scalars(select(Rom).filter_by(p_slug=p_slug, file_name=file_name)).first()

    def update_rom(self, p_slug: str, file_name: str, data: dict) -> None:
        with Session.begin() as session:
            session.query(Rom) \
                .filter(Rom.p_slug==p_slug, Rom.file_name==file_name) \
                .update(data, synchronize_session='evaluate')

    def delete_rom(self, p_slug: str, file_name: str) -> None:
        with Session.begin() as session:
            session.query(Rom) \
                .filter(Rom.p_slug==p_slug, Rom.file_name==file_name) \
                .delete(synchronize_session='evaluate')

    def purge_platforms(self, platforms: list[str]) -> None:
        log.info("Purging platforms")
        with Session.begin() as session:
            session.query(Platform) \
                .filter(Platform.slug.not_in(platforms)) \
                .delete(synchronize_session='evaluate')

    def purge_roms(self, p_slug: str, roms: list[dict]) -> None:
        log.info(f"Purging {p_slug} roms")
        with Session.begin() as session:
            session.query(Rom) \
                .filter(Rom.p_slug==p_slug, Rom.file_name.not_in([rom['file_name'] for rom in roms])) \
                .delete(synchronize_session='evaluate')
