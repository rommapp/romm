import re
from functools import cached_property

from config import FRONTEND_RESOURCES_PATH
from models.assets import Save, Screenshot, State
from models.base import BaseModel
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    ForeignKey,
    Integer,
    Float,
    String,
    Text,
    BigInteger,
)
from sqlalchemy.orm import Mapped, relationship

SORT_COMPARE_REGEX = r"^([Tt]he|[Aa]|[Aa]nd)\s"


class Rom(BaseModel):
    __tablename__ = "roms"

    id = Column(Integer(), primary_key=True, autoincrement=True)

    igdb_id: int = Column(Integer())
    sgdb_id: int = Column(Integer())

    file_name: str = Column(String(length=450), nullable=False)
    file_name_no_tags: str = Column(String(length=450), nullable=False)
    file_name_no_ext: str = Column(String(length=450), nullable=False)
    file_extension: str = Column(String(length=100), nullable=False)
    file_path: str = Column(String(length=1000), nullable=False)
    file_size_bytes: int = Column(BigInteger(), default=0, nullable=False)

    name: str = Column(String(length=350))
    slug: str = Column(String(length=400))
    summary: str = Column(Text)
    total_rating: str = Column(String(length=350))
    # aggregated_rating: str = Column(String(length=350))
    genres: JSON = Column(JSON, default=[])
    # alternative_names: JSON = Column(JSON, default=[])
    # path_artwork: str = Column(Text, default="")
    # url_artwork: str = Column(Text, default="")
    franchises: JSON = Column(JSON, default=[])
    collections: JSON = Column(JSON, default=[])
    expansions: JSON = Column(JSON, default=[])
    # path_cover_s_expansions: str = Column(Text, default="")
    # path_cover_l_expansions: str = Column(Text, default="")
    # url_cover_expansions: str = Column(Text, default="")
    dlcs: JSON = Column(JSON, default=[])
    # path_cover_s_dlcs: str = Column(Text, default="")
    # path_cover_l_dlcs: str = Column(Text, default="")
    # url_cover_dlcs: str = Column(Text, default="")
    companies: JSON = Column(JSON, default=[])
    # platforms: JSON = Column(JSON, default=[])
    first_release_date: int = Column(BigInteger(), default=0)
    # game_modes: JSON = Column(JSON, default=[])
    # player_perspectives: JSON = Column(JSON, default=[])
    # ports: JSON = Column(JSON, default=[])
    # remaster: JSON = Column(JSON, default=[])
    remakes: JSON = Column(JSON, default=[])
    # similar_games: JSON = Column(JSON, default=[])
    # language_supports: JSON = Column(JSON, default=[])
    # external_games: JSON = Column(JSON, default=[])
    # external_games_category: JSON = Column(JSON, default=[])
    # expanded_games: JSON = Column(JSON, default=[])
    # expanded_games_category: JSON = Column(JSON, default=[])

    path_cover_s: str = Column(Text, default="")
    path_cover_l: str = Column(Text, default="")
    url_cover: str = Column(Text, default="")

    revision: str = Column(String(20))
    regions: JSON = Column(JSON, default=[])
    languages: JSON = Column(JSON, default=[])
    tags: JSON = Column(JSON, default=[])

    path_screenshots: JSON = Column(JSON, default=[])
    url_screenshots: JSON = Column(JSON, default=[])

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
        return f"/api/raw/{self.full_path}"

    @cached_property
    def has_cover(self) -> bool:
        return bool(self.path_cover_s or self.path_cover_l)

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
        from handler import db_rom_handler

        if not self.igdb_id:
            return []

        with db_rom_handler.session.begin() as session:
            return session.scalars(
                db_rom_handler.get_roms(platform_id=self.platform_id).filter(
                    Rom.id != self.id,
                    Rom.igdb_id == self.igdb_id,
                )
            ).all()

    def __repr__(self) -> str:
        return self.file_name
