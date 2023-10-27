from sqlalchemy import Column, String, Integer

from config import DEFAULT_PATH_COVER_S
from .base import BaseModel


class Platform(BaseModel):
    __tablename__ = "platforms"
    igdb_id: str = Column(String(length=10), default="")
    sgdb_id: str = Column(String(length=10), default="")

    slug: str = Column(String(length=50), default="")
    name: str = Column(String(length=400), default="")

    logo_path: str = Column(String(length=1000), default=DEFAULT_PATH_COVER_S)

    n_roms: int = Column(Integer, default=0)

    fs_slug: str = Column(String(length=50), primary_key=True)

    def __repr__(self) -> str:
        return self.name
