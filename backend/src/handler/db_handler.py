import functools

from fastapi import status, HTTPException
from sqlalchemy import create_engine, select, or_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import ProgrammingError

from logger.logger import log
from config.config_loader import ConfigLoader
from models.platform import Platform
from models.rom import Rom


class DBHandler:

    def __init__(self, cl: ConfigLoader) -> None:
        self.engine = create_engine(cl.get_db_engine(), pool_pre_ping=True)
        self.session = sessionmaker(bind=self.engine, expire_on_commit=False)


    def retry(func) -> tuple:
        @functools.wraps(func)
        def wrapper(*args):
            return func(*args)
        return wrapper


    @staticmethod
    def raise_error(e: Exception) -> None:
        error: str = f"{e}"
        log.critical(error)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error)


    # ========= Platforms =========
    def add_platform(self, Platform: Platform) -> None:
        try:
            with self.session.begin() as s:
                s.merge(Platform)
        except ProgrammingError as e:
            self.raise_error(e)


    def get_platforms(self) -> list[Platform]:
        try:
            with self.session.begin() as s:
                return s.scalars(select(Platform).order_by(Platform.slug.asc())).all()
        except ProgrammingError as e:
            self.raise_error(e)
        

    def get_platform(self, slug: str) -> Platform:
        try:
            with self.session.begin() as s:
                return s.scalars(select(Platform).filter_by(slug=slug)).first()
        except ProgrammingError as e:
            self.raise_error(e)
        

    def purge_platforms(self, platforms: list[str]) -> None:
        try:
            with self.session.begin() as s:
                s.query(Platform) \
                    .filter(or_(Platform.fs_slug.not_in(platforms), 
                                Platform.fs_slug.is_(None))) \
                    .delete(synchronize_session='evaluate')
        except ProgrammingError as e:
            self.raise_error(e)


    # ========= Roms =========
    def add_rom(self, rom: Rom) -> None:
        try:
            with self.session.begin() as s:
                s.merge(rom)
        except ProgrammingError as e:
            self.raise_error(e)


    def get_roms(self, p_slug: str) -> list[Rom]:
        try:
            with self.session.begin() as s:
                return s.scalars(select(Rom).filter_by(p_slug=p_slug).order_by(Rom.file_name.asc())).all()
        except ProgrammingError as e:
            self.raise_error(e)


    def get_rom(self, id) -> Rom:
        try:
            with self.session.begin() as s:
                return s.scalars(select(Rom).filter_by(id=id)).first()
        except ProgrammingError as e:
            self.raise_error(e)


    def update_rom(self, id: int, data: dict) -> None:
        try:
            with self.session.begin() as s:
                s.query(Rom) \
                    .filter(Rom.id==id).update(data, synchronize_session='evaluate')
        except ProgrammingError as e:
            self.raise_error(e)


    def delete_rom(self, id: int) -> None:
        try:
            with self.session.begin() as s:
                s.query(Rom) \
                    .filter(Rom.id==id).delete(synchronize_session='evaluate')
        except ProgrammingError as e:
            self.raise_error(e)


    def purge_roms(self, p_slug: str, roms: list[str]) -> None:
        try:
            with self.session.begin() as s:
                s.query(Rom) \
                    .filter(Rom.p_slug==p_slug, Rom.file_name.not_in(roms)) \
                    .delete(synchronize_session='evaluate')
        except ProgrammingError as e:
            self.raise_error(e)


    # ==== Utils ======
    def rom_exists(self, platform: str, file_name: str) -> int:
        try:
            with self.session.begin() as s:
                rom = s.scalar(select(Rom).filter_by(p_slug=platform, file_name=file_name))
                return rom.id if rom else None
        except ProgrammingError as e:
            self.raise_error(e)