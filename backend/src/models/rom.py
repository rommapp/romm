from sqlalchemy import Column, String, Text, Boolean, Float, JSON

from config import DEFAULT_PATH_COVER_S, DEFAULT_PATH_COVER_L
from models.base import BaseModel


class Rom(BaseModel):
    __tablename__ = 'roms'
    r_igdb_id = Column(String(length=10), default="")
    p_igdb_id = Column(String(length=10), default="")
    r_sgdb_id = Column(String(length=10), default="")
    p_sgdb_id = Column(String(length=10), default="")

    p_slug = Column(String(length=50), primary_key=True)

    file_name = Column(String(length=450), primary_key=True)
    file_name_no_tags = Column(String(length=450), default="")
    file_extension = Column(String(length=10), default="")
    file_path = Column(String(length=1000), default="")
    file_size = Column(Float, default=0.0)
    
    name = Column(String(length=350), default="")
    r_slug = Column(String(length=100), default="")

    summary = Column(Text, default="")

    path_cover_s = Column(Text, default=DEFAULT_PATH_COVER_S)
    path_cover_l = Column(Text, default=DEFAULT_PATH_COVER_L)
    has_cover = Column(Boolean, default=False)
    
    region = Column(String(20), default="")
    revision = Column(String(20), default="")
    tags = Column(JSON, default=[])

    multi = Column(Boolean, default=False)
    files = Column(JSON, default=[])

    @property
    def full_path(self) -> str:
        return f"{self.file_path}/{self.file_name}"

    def __repr__(self) -> str:
        return (
            f"r_igdb_id: {self.r_igdb_id},"
            f"p_igdb_id: {self.p_igdb_id},"
            f"r_slug: {self.r_slug},"
            f"p_slug: {self.p_slug},"
            f"file_name: {self.file_name},"
            f"file_path: {self.file_path},"
            f"multi: {self.multi},"
            f"files: {self.files}"
        )
