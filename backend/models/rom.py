import re
from functools import cached_property

from config import (
    DEFAULT_PATH_COVER_L,
    DEFAULT_PATH_COVER_S,
    FRONTEND_LIBRARY_PATH,
    FRONTEND_RESOURCES_PATH,
)
from models.assets import Save, Screenshot, State
from models.base import BaseModel
from sqlalchemy import JSON, Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, relationship

SORT_COMPARE_REGEX = r"^([Tt]he|[Aa]|[Aa]nd)\s"


class Rom(BaseModel):
    __tablename__ = "roms"

    id = Column(Integer(), primary_key=True, autoincrement=True)

    igdb_id: int = Column(Integer())
    sgdb_id: int = Column(Integer())

    file_name: str = Column(String(length=450), nullable=False)
    file_name_no_tags: str = Column(String(length=450), nullable=False)
    file_extension: str = Column(String(length=100), nullable=False)
    file_path: str = Column(String(length=1000), nullable=False)
    file_size_bytes: int = Column(Integer(), default=0, nullable=False)

    name: str = Column(String(length=350))
    slug: str = Column(String(length=400))
    summary: str = Column(Text)

    path_cover_s: str = Column(Text, default=DEFAULT_PATH_COVER_S)
    path_cover_l: str = Column(Text, default=DEFAULT_PATH_COVER_L)
    url_cover: str = Column(Text, default=DEFAULT_PATH_COVER_L)

    revision: str = Column(String(20))
    regions: JSON = Column(JSON, default=[])
    languages: JSON = Column(JSON, default=[])
    tags: JSON = Column(JSON, default=[])

    url_screenshots: JSON = Column(JSON, default=[])
    path_screenshots: JSON = Column(JSON, default=[])

    multi: bool = Column(Boolean, default=False)
    files: JSON = Column(JSON, default=[])

    platform_id = Column(
        Integer(),
        ForeignKey("platforms.id", ondelete="CASCADE"),
        nullable=False,
    )

    platform = relationship("Platform", lazy="selectin", back_populates="roms")

    saves: Mapped[list[Save]] = relationship(
        "Save",
        lazy="selectin",
        back_populates="rom",
    )
    states: Mapped[list[State]] = relationship(
        "State", lazy="selectin", back_populates="rom"
    )
    screenshots: Mapped[list[Screenshot]] = relationship(
        "Screenshot", lazy="selectin", back_populates="rom"
    )

    @property
    def platform_slug(self) -> str:
        return self.platform.slug

    @property
    def platform_fs_slug(self) -> str:
        return self.platform.fs_slug

    @property
    def platform_name(self) -> str:
        return self.platform.name

    @cached_property
    def full_path(self) -> str:
        return f"{self.file_path}/{self.file_name}"

    @cached_property
    def download_path(self) -> str:
        return f"{FRONTEND_LIBRARY_PATH}/{self.full_path}"

    @cached_property
    def has_cover(self) -> bool:
        return (
            self.path_cover_s != DEFAULT_PATH_COVER_S
            or self.path_cover_l != DEFAULT_PATH_COVER_L
        )

    @cached_property
    def merged_screenshots(self) -> list[str]:
        return [s.download_path for s in self.screenshots] + [
            f"{FRONTEND_RESOURCES_PATH}/{s}" for s in self.path_screenshots
        ]

    @cached_property
    def sort_comparator(self) -> str:
        return (
            re.sub(
                SORT_COMPARE_REGEX,
                "",
                self.name or self.file_name_no_tags,
            )
            .strip()
            .lower()
        )

    # This is an expensive operation so don't call it on a list of roms
    @cached_property
    def sibling_roms(self) -> list["Rom"]:
        from handler import dbromh

        if not self.igdb_id:
            return []

        with dbromh.session.begin() as session:
            return session.scalars(
                dbromh.get_roms(platform_id=self.platform_id).filter(
                    Rom.id != self.id,
                    Rom.igdb_id == self.igdb_id,
                )
            ).all()

    def __repr__(self) -> str:
        return self.file_name
