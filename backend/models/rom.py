import re
from sqlalchemy import Integer, Column, String, Text, Boolean, Float, JSON, ForeignKey
from sqlalchemy.orm import relationship, Mapped
from functools import cached_property

from config import DEFAULT_PATH_COVER_S, DEFAULT_PATH_COVER_L, FRONT_LIBRARY_PATH
from .base import BaseModel

SIZE_UNIT_TO_BYTES = {
    "B": 1,
    "KB": 1024,
    "MB": 1024 ^ 2,
    "GB": 1024 ^ 3,
    "TB": 1024 ^ 4,
    "PB": 1024 ^ 5,
}

SORT_COMPARE_REGEX = r"^([Tt]he|[Aa]|[Aa]nd)\s"


class Rom(BaseModel):
    from .assets import Save, State, Screenshot

    __tablename__ = "roms"

    id = Column(Integer(), primary_key=True, autoincrement=True)

    igdb_id: int = Column(Integer())
    sgdb_id: int = Column(Integer())

    platform_slug = Column(
        String(length=50),
        ForeignKey("platforms.slug", ondelete="CASCADE"),
        nullable=False,
    )
    platform = relationship(
        "Platform", lazy="joined", innerjoin=True, back_populates="roms"
    )

    saves: Mapped[list[Save]] = relationship(
        "Save",
        lazy="joined",
        innerjoin=True,
        back_populates="rom",
    )
    states: Mapped[list[State]] = relationship(
        "State", lazy="joined", innerjoin=True, back_populates="rom"
    )
    screenshots: Mapped[list[Screenshot]] = relationship(
        "Screenshot", lazy="joined", innerjoin=True, back_populates="rom"
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
    def file_size_bytes(self) -> int:
        return int(self.file_size * SIZE_UNIT_TO_BYTES[self.file_size_units or "B"])

    @property
    def has_cover(self) -> bool:
        return (
            self.path_cover_s != DEFAULT_PATH_COVER_S
            or self.path_cover_l != DEFAULT_PATH_COVER_L
        )

    # @property
    # def screenshots(self) -> list[str]:
    #     return self.path_screenshots

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

    def __repr__(self) -> str:
        return self.file_name
