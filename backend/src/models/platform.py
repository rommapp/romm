from sqlalchemy import Column, String, Integer

from config import DEFAULT_PATH_COVER_S
from models.base import BaseModel


class Platform(BaseModel):
    __tablename__ = 'platforms'
    igdb_id = Column(String(length=10), default="")
    sgdb_id = Column(String(length=10), default="")

    slug = Column(String(length=50), primary_key=True)
    name = Column(String(length=400), default="")

    logo_path = Column(String(length=1000), default=DEFAULT_PATH_COVER_S)
    
    n_roms = Column(Integer, default=0)

    def __repr__(self) -> str:
        return self.name
