from __future__ import annotations

import enum
from datetime import datetime
from functools import cached_property
from typing import TYPE_CHECKING, Any

from config import FRONTEND_RESOURCES_PATH
from models.base import BaseModel
from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.database import CustomJSON, safe_float, safe_int

if TYPE_CHECKING:
    from models.assets import Save, Screenshot, State
    from models.collection import Collection
    from models.platform import Platform
    from models.user import User


class RomFileCategory(enum.StrEnum):
    DLC = "dlc"
    HACK = "hack"
    MANUAL = "manual"
    PATCH = "patch"
    UPDATE = "update"
    MOD = "mod"
    DEMO = "demo"
    TRANSLATION = "translation"
    PROTOTYPE = "prototype"


class RomFile(BaseModel):
    __tablename__ = "rom_files"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    rom_id: Mapped[int] = mapped_column(ForeignKey("roms.id", ondelete="CASCADE"))
    file_name: Mapped[str] = mapped_column(String(length=450))
    file_path: Mapped[str] = mapped_column(String(length=1000))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger(), default=0)
    last_modified: Mapped[float | None] = mapped_column(default=None)
    crc_hash: Mapped[str | None] = mapped_column(String(100))
    md5_hash: Mapped[str | None] = mapped_column(String(100))
    sha1_hash: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[RomFileCategory | None] = mapped_column(
        Enum(RomFileCategory), default=None
    )

    rom: Mapped[Rom] = relationship(lazy="joined")

    @cached_property
    def full_path(self) -> str:
        return f"{self.file_path}/{self.file_name}"

    def file_name_for_download(self, rom: Rom, hidden_folder: bool = False) -> str:
        # This needs a trailing slash in the path to work!
        return self.full_path.replace(
            f"{rom.full_path}/", ".hidden/" if hidden_folder else ""
        )


class Rom(BaseModel):
    __tablename__ = "roms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    igdb_id: Mapped[int | None]
    sgdb_id: Mapped[int | None]
    moby_id: Mapped[int | None]
    ss_id: Mapped[int | None]

    __table_args__ = (
        Index("idx_roms_igdb_id", "igdb_id"),
        Index("idx_roms_moby_id", "moby_id"),
        Index("idx_roms_ss_id", "ss_id"),
    )

    fs_name: Mapped[str] = mapped_column(String(length=450))
    fs_name_no_tags: Mapped[str] = mapped_column(String(length=450))
    fs_name_no_ext: Mapped[str] = mapped_column(String(length=450))
    fs_extension: Mapped[str] = mapped_column(String(length=100))
    fs_path: Mapped[str] = mapped_column(String(length=1000))

    name: Mapped[str | None] = mapped_column(String(length=350))
    slug: Mapped[str | None] = mapped_column(String(length=400))
    summary: Mapped[str | None] = mapped_column(Text)
    igdb_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        CustomJSON(), default=dict
    )
    moby_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        CustomJSON(), default=dict
    )
    ss_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        CustomJSON(), default=dict
    )

    path_cover_s: Mapped[str | None] = mapped_column(Text, default="")
    path_cover_l: Mapped[str | None] = mapped_column(Text, default="")
    url_cover: Mapped[str | None] = mapped_column(
        Text, default="", doc="URL to cover image stored in IGDB"
    )

    path_manual: Mapped[str | None] = mapped_column(Text, default="")
    url_manual: Mapped[str | None] = mapped_column(
        Text, default="", doc="URL to manual stored in ScreenScraper"
    )

    revision: Mapped[str | None] = mapped_column(String(length=100))
    regions: Mapped[list[str] | None] = mapped_column(CustomJSON(), default=[])
    languages: Mapped[list[str] | None] = mapped_column(CustomJSON(), default=[])
    tags: Mapped[list[str] | None] = mapped_column(CustomJSON(), default=[])

    path_screenshots: Mapped[list[str] | None] = mapped_column(CustomJSON(), default=[])
    url_screenshots: Mapped[list[str] | None] = mapped_column(
        CustomJSON(), default=[], doc="URLs to screenshots stored in IGDB"
    )

    crc_hash: Mapped[str | None] = mapped_column(String(length=100))
    md5_hash: Mapped[str | None] = mapped_column(String(length=100))
    sha1_hash: Mapped[str | None] = mapped_column(String(length=100))

    platform_id: Mapped[int] = mapped_column(
        ForeignKey("platforms.id", ondelete="CASCADE")
    )

    platform: Mapped[Platform] = relationship(lazy="immediate")
    sibling_roms: Mapped[list[Rom]] = relationship(
        secondary="sibling_roms",
        primaryjoin="Rom.id == SiblingRom.rom_id",
        secondaryjoin="Rom.id == SiblingRom.sibling_rom_id",
    )
    files: Mapped[list[RomFile]] = relationship(lazy="immediate", back_populates="rom")
    saves: Mapped[list[Save]] = relationship(back_populates="rom")
    states: Mapped[list[State]] = relationship(back_populates="rom")
    screenshots: Mapped[list[Screenshot]] = relationship(back_populates="rom")
    rom_users: Mapped[list[RomUser]] = relationship(back_populates="rom")

    collections: Mapped[list[Collection]] = relationship(
        "Collection",
        secondary="collections_roms",
        collection_class=set,
        back_populates="roms",
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

    @property
    def platform_custom_name(self) -> str | None:
        return self.platform.custom_name

    @property
    def platform_display_name(self) -> str:
        return self.platform.custom_name or self.platform.name

    @cached_property
    def full_path(self) -> str:
        return f"{self.fs_path}/{self.fs_name}"

    @cached_property
    def has_manual(self) -> bool:
        return bool(self.path_manual)

    @cached_property
    def merged_screenshots(self) -> list[str]:
        screenshots = [s.download_path for s in self.screenshots]
        if self.path_screenshots:
            screenshots += [
                f"{FRONTEND_RESOURCES_PATH}/{s}" for s in self.path_screenshots
            ]
        return screenshots

    @cached_property
    def multi(self) -> bool:
        return len(self.files) > 1

    @cached_property
    def fs_size_bytes(self) -> int:
        return sum(f.file_size_bytes for f in self.files)

    @property
    def fs_resources_path(self) -> str:
        return f"roms/{str(self.platform_id)}/{str(self.id)}"

    @property
    def path_cover_small(self) -> str:
        return (
            f"{FRONTEND_RESOURCES_PATH}/{self.path_cover_s}?ts={self.updated_at}"
            if self.path_cover_s
            else ""
        )

    @property
    def path_cover_large(self) -> str:
        return (
            f"{FRONTEND_RESOURCES_PATH}/{self.path_cover_l}?ts={self.updated_at}"
            if self.path_cover_l
            else ""
        )

    # Metadata fields
    @property
    def youtube_video_id(self) -> str:
        if self.igdb_metadata:
            return self.igdb_metadata.get("youtube_video_id", "")
        return ""

    @property
    def alternative_names(self) -> list[str]:
        return (
            (self.igdb_metadata or {}).get("alternative_names", None)
            or (self.moby_metadata or {}).get("alternate_titles", None)
            or (self.ss_metadata or {}).get("alternative_names", None)
            or []
        )

    @property
    def first_release_date(self) -> int | None:
        if self.igdb_metadata:
            return safe_int(self.igdb_metadata.get("first_release_date") or 0) * 1000
        elif self.ss_metadata:
            return safe_int(self.ss_metadata.get("first_release_date") or 0) * 1000

        return None

    @property
    def average_rating(self) -> float | None:
        igdb_rating = (
            safe_float(self.igdb_metadata.get("total_rating") or 0)
            if self.igdb_metadata
            else 0.0
        )
        moby_rating = (
            safe_float(self.moby_metadata.get("moby_score") or 0)
            if self.moby_metadata
            else 0.0
        )
        ss_rating = (
            safe_float(self.ss_metadata.get("ss_score") or 0)
            if self.ss_metadata
            else 0.0
        )

        ratings = [r for r in [igdb_rating, moby_rating * 10, ss_rating] if r != 0.0]

        return sum(ratings) / len([r for r in ratings if r]) if any(ratings) else None

    @property
    def genres(self) -> list[str]:
        return (
            (self.igdb_metadata or {}).get("genres", None)
            or (self.moby_metadata or {}).get("genres", None)
            or (self.ss_metadata or {}).get("genres", None)
            or []
        )

    @property
    def franchises(self) -> list[str]:
        if self.igdb_metadata:
            return self.igdb_metadata.get("franchises", [])
        elif self.ss_metadata:
            return self.ss_metadata.get("franchises", [])
        return []

    @property
    def meta_collections(self) -> list[str]:
        if self.igdb_metadata:
            return self.igdb_metadata.get("collections", [])
        return []

    @property
    def companies(self) -> list[str]:
        if self.igdb_metadata:
            return self.igdb_metadata.get("companies", [])
        elif self.ss_metadata:
            return self.ss_metadata.get("companies", [])
        return []

    @property
    def game_modes(self) -> list[str]:
        if self.igdb_metadata:
            return self.igdb_metadata.get("game_modes", [])
        elif self.ss_metadata:
            return self.ss_metadata.get("game_modes", [])
        return []

    @property
    def age_ratings(self) -> list[str]:
        if self.igdb_metadata:
            return [r["rating"] for r in self.igdb_metadata.get("age_ratings", [])]
        return []

    @property
    def is_unidentified(self) -> bool:
        return not self.igdb_id and not self.moby_id and not self.ss_id

    @property
    def is_partially_identified(self) -> bool:
        return not self.is_unidentified and not self.is_fully_identified

    @property
    def is_fully_identified(self) -> bool:
        return bool(self.igdb_id) and bool(self.moby_id) and bool(self.ss_id)

    def __repr__(self) -> str:
        return self.fs_name


class RomUserStatus(enum.StrEnum):
    INCOMPLETE = "incomplete"  # Started but not finished
    FINISHED = "finished"  # Reached the end of the game
    COMPLETED_100 = "completed_100"  # Completed 100%
    RETIRED = "retired"  # Won't play again
    NEVER_PLAYING = "never_playing"  # Will never play


class RomUser(BaseModel):
    __tablename__ = "rom_user"
    __table_args__ = (
        UniqueConstraint("rom_id", "user_id", name="unique_rom_user_props"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    note_raw_markdown: Mapped[str] = mapped_column(Text, default="")
    note_is_public: Mapped[bool] = mapped_column(default=False)

    is_main_sibling: Mapped[bool] = mapped_column(default=False)
    last_played: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    backlogged: Mapped[bool] = mapped_column(default=False)
    now_playing: Mapped[bool] = mapped_column(default=False)
    hidden: Mapped[bool] = mapped_column(default=False)
    rating: Mapped[int] = mapped_column(default=0)
    difficulty: Mapped[int] = mapped_column(default=0)
    completion: Mapped[int] = mapped_column(default=0)
    status: Mapped[RomUserStatus | None] = mapped_column(
        Enum(RomUserStatus), default=None
    )

    rom_id: Mapped[int] = mapped_column(ForeignKey("roms.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    rom: Mapped[Rom] = relationship(lazy="joined", back_populates="rom_users")
    user: Mapped[User] = relationship(lazy="joined", back_populates="rom_users")

    @property
    def user__username(self) -> str:
        return self.user.username


class SiblingRom(BaseModel):
    __tablename__ = "sibling_roms"

    rom_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sibling_rom_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    __table_args__ = (
        UniqueConstraint("rom_id", "sibling_rom_id", name="unique_sibling_roms"),
    )
