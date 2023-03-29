from sqlalchemy import Column, String, Integer, Text

from config.config import DEFAULT_PATH_COVER
from models.base import BaseModel


class Platform(BaseModel):
    __tablename__ = 'platforms'
    igdb_id = Column(String(length=50), default="")
    sgdb_id = Column(String(length=50), default="")
    slug = Column(String(length=100), primary_key=True)
    name = Column(String(length=350), default="")
    path_logo = Column(Text, default=DEFAULT_PATH_COVER)
    n_roms = Column(Integer, default=0)
