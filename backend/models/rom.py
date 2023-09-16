from sqlalchemy import Integer, Column, String, Text, Boolean, Float, JSON, ForeignKey
from sqlalchemy.orm import relationship, Mapped
from functools import cached_property

from config import DEFAULT_PATH_COVER_S, DEFAULT_PATH_COVER_L, FRONT_LIBRARY_PATH
from .base import BaseModel


class Rom(BaseModel):
    from .platform import Platform

    __tablename__ = "roms"
    id = Column(Integer(), primary_key=True, autoincrement=True)

    igdb_id: str = Column(Integer())
    sgdb_id: str = Column(Integer())

    # Foreign key to platform
    platform_slug = Column(
        String(length=50), ForeignKey("platforms.slug"), nullable=False
    )
    platform: Mapped[Platform] = relationship(  # noqa
        "Platform", lazy="joined", innerjoin=True
    )

    ### DEPRECATED ###
    p_name: str = Column(String(length=150), default="")
    p_igdb_id: str = Column(String(length=10), default="")
    p_sgdb_id: str = Column(String(length=10), default="")
    ### DEPRECATED ###

    file_name: str = Column(String(length=450), nullable=False)
    file_name_no_tags: str = Column(String(length=450), nullable=False)
    file_extension: str = Column(String(length=10), nullable=False)
    file_path: str = Column(String(length=1000), nullable=False)
    file_size = Column(Float, default=0.0, nullable=False)
    file_size_units: str = Column(String(length=10), nullable=False)

    name: str = Column(String(length=350))
    slug: str = Column(String(length=400))
    summary: str = Column(Text)

    path_cover_s: str = Column(Text, default=DEFAULT_PATH_COVER_S)
    path_cover_l: str = Column(Text, default=DEFAULT_PATH_COVER_L)
    url_cover: str = Column(Text, default=DEFAULT_PATH_COVER_L)

    region: str = Column(String(20))
    revision: str = Column(String(20))
    tags: JSON = Column(JSON, default=[])
    multi: bool = Column(Boolean, default=False)
    files: JSON = Column(JSON, default=[])
    url_screenshots: JSON = Column(JSON, default=[])
    path_screenshots: JSON = Column(JSON, default=[])

    @property
    def platform_name(self) -> str:
        return self.platform.name

    @cached_property
    def full_path(self) -> str:
        return f"{self.file_path}/{self.file_name}"

    @cached_property
    def download_path(self) -> str:
        return f"{FRONT_LIBRARY_PATH}/{self.full_path}"

    @property
    def has_cover(self) -> bool:
        return (
            self.path_cover_s != DEFAULT_PATH_COVER_S
            or self.path_cover_l != DEFAULT_PATH_COVER_L
        )

    def __repr__(self) -> str:
        return self.file_name
