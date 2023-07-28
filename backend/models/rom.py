from sqlalchemy import Integer, Column, String, Text, Boolean, Float, JSON

from config import DEFAULT_PATH_COVER_S, DEFAULT_PATH_COVER_L, FRONT_LIBRARY_PATH
from models.base import BaseModel


class Rom(BaseModel):
    __tablename__ = 'roms'
    id = Column(Integer(), primary_key=True, autoincrement=True)

    r_igdb_id = Column(String(length=10), default="")
    p_igdb_id = Column(String(length=10), default="")
    r_sgdb_id = Column(String(length=10), default="")
    p_sgdb_id = Column(String(length=10), default="")

    p_slug = Column(String(length=50))
    p_name = Column(String(length=150), default="")

    file_name = Column(String(length=450), nullable=False)
    file_name_no_tags = Column(String(length=450))
    file_extension = Column(String(length=10), default="")
    file_path = Column(String(length=1000), default="")
    file_size = Column(Float, default=0.0)
    file_size_units = Column(String(length=10), default="")
    
    r_name = Column(String(length=350), default="")
    r_slug = Column(String(length=400), default="")

    summary = Column(Text, default="")

    path_cover_s = Column(Text, default=DEFAULT_PATH_COVER_S)
    path_cover_l = Column(Text, default=DEFAULT_PATH_COVER_L)
    has_cover = Column(Boolean, default=False)
    url_cover = Column(Text, default=DEFAULT_PATH_COVER_L)
    
    region = Column(String(20), default="")
    revision = Column(String(20), default="")
    tags = Column(JSON, default=[])

    multi = Column(Boolean, default=False)
    files = Column(JSON, default=[])

    url_screenshots = Column(JSON, default=[])
    path_screenshots = Column(JSON, default=[])

    @property
    def full_path(self) -> str:
        return f"{self.file_path}/{self.file_name}"

    @property
    def download_path(self) -> str:
        return f"{FRONT_LIBRARY_PATH}/{self.full_path}"

    def __repr__(self) -> str:
        return self.file_name
