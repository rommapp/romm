import functools

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from config.config_loader import ConfigLoader
from models.platform import Platform
from models.rom import Rom


class DBHandler:

    def __init__(self) -> None:
        cl = ConfigLoader()
        self.engine = create_engine(cl.get_db_engine(), pool_pre_ping=True)
        self.session = sessionmaker(bind=self.engine, expire_on_commit=False)


    def retry(func) -> tuple:
        @functools.wraps(func)
        def wrapper(*args):
            return func(*args)
        return wrapper


    # ========= Platforms =========
    def add_platform(self, Platform: Platform) -> None:
        try:
            with self.session.begin() as s:
                s.merge(Platform)
        except ProgrammingError as e:
            raise HTTPException(status_code=404, detail=f"Platforms table not found: {e}")

    def get_platforms(self) -> list[Platform]:
        try:
            with self.session.begin() as s:
                return s.scalars(select(Platform).order_by(Platform.slug.asc())).all()
        except ProgrammingError as e:
            raise HTTPException(status_code=404, detail=f"Platforms table not found: {e}")
        
    def get_platform(self, slug: str) -> Platform:
        try:
            with self.session.begin() as s:
                return s.scalars(select(Platform).filter_by(slug=slug)).first()
        except ProgrammingError as e:
            raise HTTPException(status_code=404, detail=f"Platforms table not found: {e}")
        
    def purge_platforms(self, platforms: list[str]) -> None:
        with self.session.begin() as s:
            s.query(Platform) \
                .filter(Platform.slug.not_in(platforms)) \
                .delete(synchronize_session='evaluate')

    # ========= Roms =========
    def add_rom(self, rom: Rom) -> None:
        with self.session.begin() as s:
            s.merge(rom)

    def get_roms(self, p_slug: str) -> list[Rom]:
        with self.session.begin() as s:
            return s.scalars(select(Rom).filter_by(p_slug=p_slug).order_by(Rom.file_name.asc())).all()

    def get_rom(self, p_slug: str, file_name: str) -> Rom:
        with self.session.begin() as s:
            return s.scalars(select(Rom).filter_by(p_slug=p_slug, file_name=file_name)).first()

    def update_rom(self, p_slug: str, file_name: str, data: dict) -> None:
        with self.session.begin() as s:
            s.query(Rom) \
                .filter(Rom.p_slug==p_slug, Rom.file_name==file_name) \
                .update(data, synchronize_session='evaluate')

    def delete_rom(self, p_slug: str, file_name: str) -> None:
        with self.session.begin() as s:
            s.query(Rom) \
                .filter(Rom.p_slug==p_slug, Rom.file_name==file_name) \
                .delete(synchronize_session='evaluate')

    def purge_roms(self, p_slug: str, roms: list[dict]) -> None:
        with self.session.begin() as s:
            s.query(Rom) \
                .filter(Rom.p_slug==p_slug, Rom.file_name.not_in([rom['file_name'] for rom in roms])) \
                .delete(synchronize_session='evaluate')
