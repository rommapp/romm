from sqlalchemy import Column, String, Integer

from config import DEFAULT_PATH_COVER_S
from .base import BaseModel


class Platform(BaseModel):
    __tablename__ = "platforms"

    slug: str = Column(String(length=50), primary_key=True)
    fs_slug: str = Column(String(length=50), nullable=False)
    name: str = Column(String(length=400))
    igdb_id: str = Column(String(length=10))
    sgdb_id: str = Column(String(length=10))
    logo_path: str = Column(String(length=1000), default=DEFAULT_PATH_COVER_S)

    ### DEPRECATED ###
    n_roms: int = Column(Integer, default=0)
    ### DEPRECATED ###

    @property
    def rom_count(self) -> int:
        from handler import dbh

        return dbh.get_rom_count(self.slug)

    def __repr__(self) -> str:
        return self.name
