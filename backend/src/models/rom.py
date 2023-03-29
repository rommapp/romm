from sqlalchemy import Column, String, Text, Boolean

from config.config import DEFAULT_PATH_COVER_S, DEFAULT_PATH_COVER_L
from models.base import BaseModel


class Rom(BaseModel):
    __tablename__ = 'roms'
    filename = Column(String(length=500), primary_key=True)
    filename_no_ext = Column(String(length=500), default="")
    r_igdb_id = Column(String(length=50), default="")
    p_igdb_id = Column(String(length=50), default="")
    r_sgdb_id = Column(String(length=50), default="")
    p_sgdb_id = Column(String(length=50), default="")
    name = Column(String(length=500), default="")
    r_slug = Column(String(length=500), default="")
    p_slug = Column(String(length=500), primary_key=True)
    summary = Column(Text, default="")
    path_cover_s = Column(Text, default=DEFAULT_PATH_COVER_S)
    path_cover_l = Column(Text, default=DEFAULT_PATH_COVER_L)
    has_cover = Column(Boolean, default=False)
    size = Column(String(length=20), default="")
