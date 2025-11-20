from __future__ import annotations

import enum
from datetime import datetime
from functools import cached_property
from typing import TYPE_CHECKING, Any

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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config import FRONTEND_RESOURCES_PATH
from models.base import (
    FILE_EXTENSION_MAX_LENGTH,
    FILE_NAME_MAX_LENGTH,
    FILE_PATH_MAX_LENGTH,
    BaseModel,
)
from utils.database import CustomJSON

if TYPE_CHECKING:
    from models.assets import Save, Screenshot, State
    from models.collection import Collection
    from models.platform import Platform
    from models.user import User


class RomFileCategory(enum.StrEnum):
    GAME = "game"
    DLC = "dlc"
    HACK = "hack"
    MANUAL = "manual"
    PATCH = "patch"
    UPDATE = "update"
    MOD = "mod"
    DEMO = "demo"
    TRANSLATION = "translation"
    PROTOTYPE = "prototype"


class SiblingRom(BaseModel):
    __tablename__ = "sibling_roms"

    rom_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sibling_rom_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    __table_args__ = (
        UniqueConstraint("rom_id", "sibling_rom_id", name="unique_sibling_roms"),
    )


class RomFile(BaseModel):
    __tablename__ = "rom_files"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    rom_id: Mapped[int] = mapped_column(ForeignKey("roms.id", ondelete="CASCADE"))
    file_name: Mapped[str] = mapped_column(String(length=FILE_NAME_MAX_LENGTH))
    file_path: Mapped[str] = mapped_column(String(length=FILE_PATH_MAX_LENGTH))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger(), default=0)
    last_modified: Mapped[float | None] = mapped_column(default=None)
    crc_hash: Mapped[str | None] = mapped_column(String(100))
    md5_hash: Mapped[str | None] = mapped_column(String(100))
    sha1_hash: Mapped[str | None] = mapped_column(String(100))
    ra_hash: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[RomFileCategory | None] = mapped_column(
        Enum(RomFileCategory), default=None
    )
    missing_from_fs: Mapped[bool] = mapped_column(default=False, nullable=False)

    rom: Mapped[Rom] = relationship(lazy="joined", back_populates="files")

    @cached_property
    def full_path(self) -> str:
        return f"{self.file_path}/{self.file_name}"

    @cached_property
    def file_name_no_tags(self) -> str:
        from handler.filesystem import fs_rom_handler

        return fs_rom_handler.get_file_name_with_no_tags(self.file_name)

    @cached_property
    def file_name_no_ext(self) -> str:
        from handler.filesystem import fs_rom_handler

        return fs_rom_handler.get_file_name_with_no_extension(self.file_name)

    @cached_property
    def file_extension(self) -> str:
        from handler.filesystem import fs_rom_handler

        return fs_rom_handler.parse_file_extension(self.file_name)

    @cached_property
    def is_nested(self) -> bool:
        return self.file_path.count("/") > 1

    @cached_property
    def is_top_level(self) -> bool:
        # File is the same as the rom's full path, or nested file in the rom's directory
        return self.rom.full_path == (
            self.file_path if self.is_nested else self.full_path
        )

    def file_name_for_download(self, hidden_folder: bool = False) -> str:
        # This needs a trailing slash in the path to work!
        return self.full_path.replace(
            f"{self.rom.full_path}/", ".hidden/" if hidden_folder else ""
        )

    def __repr__(self) -> str:
        return f"{self.file_name} ({self.id} -> {self.rom_id})"


class RomMetadata(BaseModel):
    __tablename__ = "roms_metadata"

    rom_id: Mapped[int] = mapped_column(
        ForeignKey("roms.id", ondelete="CASCADE"), primary_key=True
    )

    genres: Mapped[list[str] | None] = mapped_column(CustomJSON(), default=[])
    franchises: Mapped[list[str] | None] = mapped_column(CustomJSON(), default=[])
    collections: Mapped[list[str] | None] = mapped_column(CustomJSON(), default=[])
    companies: Mapped[list[str] | None] = mapped_column(CustomJSON(), default=[])
    game_modes: Mapped[list[str] | None] = mapped_column(CustomJSON(), default=[])
    age_ratings: Mapped[list[str] | None] = mapped_column(CustomJSON(), default=[])
    first_release_date: Mapped[int | None] = mapped_column(BigInteger(), default=None)
    average_rating: Mapped[float | None] = mapped_column(default=None)

    rom: Mapped[Rom] = relationship(lazy="joined", back_populates="metadatum")


class Rom(BaseModel):
    __tablename__ = "roms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    igdb_id: Mapped[int | None] = mapped_column(Integer(), default=None)
    sgdb_id: Mapped[int | None] = mapped_column(Integer(), default=None)
    moby_id: Mapped[int | None] = mapped_column(Integer(), default=None)
    ss_id: Mapped[int | None] = mapped_column(Integer(), default=None)
    ra_id: Mapped[int | None] = mapped_column(Integer(), default=None)
    launchbox_id: Mapped[int | None] = mapped_column(Integer(), default=None)
    hasheous_id: Mapped[int | None] = mapped_column(Integer(), default=None)
    tgdb_id: Mapped[int | None] = mapped_column(Integer(), default=None)
    flashpoint_id: Mapped[str | None] = mapped_column(String(length=100), default=None)
    hltb_id: Mapped[int | None] = mapped_column(Integer(), default=None)
    gamelist_id: Mapped[str | None] = mapped_column(String(length=100), default=None)

    __table_args__ = (
        Index("idx_roms_igdb_id", "igdb_id"),
        Index("idx_roms_moby_id", "moby_id"),
        Index("idx_roms_ss_id", "ss_id"),
        Index("idx_roms_ra_id", "ra_id"),
        Index("idx_roms_sgdb_id", "sgdb_id"),
        Index("idx_roms_launchbox_id", "launchbox_id"),
        Index("idx_roms_hasheous_id", "hasheous_id"),
        Index("idx_roms_tgdb_id", "tgdb_id"),
        Index("idx_roms_flashpoint_id", "flashpoint_id"),
        Index("idx_roms_hltb_id", "hltb_id"),
        Index("idx_roms_gamelist_id", "gamelist_id"),
    )

    fs_name: Mapped[str] = mapped_column(String(length=FILE_NAME_MAX_LENGTH))
    fs_name_no_tags: Mapped[str] = mapped_column(String(length=FILE_NAME_MAX_LENGTH))
    fs_name_no_ext: Mapped[str] = mapped_column(String(length=FILE_NAME_MAX_LENGTH))
    fs_extension: Mapped[str] = mapped_column(String(length=FILE_EXTENSION_MAX_LENGTH))
    fs_path: Mapped[str] = mapped_column(String(length=FILE_PATH_MAX_LENGTH))
    fs_size_bytes: Mapped[int] = mapped_column(BigInteger(), default=0)

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
    ra_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        CustomJSON(), default=dict
    )
    launchbox_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        CustomJSON(), default=dict
    )
    hasheous_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        CustomJSON(), default=dict
    )
    flashpoint_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        CustomJSON(), default=dict
    )
    hltb_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        CustomJSON(), default=dict
    )
    gamelist_metadata: Mapped[dict[str, Any] | None] = mapped_column(
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

    path_screenshots: Mapped[list[str] | None] = mapped_column(CustomJSON(), default=[])
    url_screenshots: Mapped[list[str] | None] = mapped_column(
        CustomJSON(), default=[], doc="URLs to screenshots stored in IGDB"
    )

    revision: Mapped[str | None] = mapped_column(String(length=100))
    regions: Mapped[list[str] | None] = mapped_column(CustomJSON(), default=[])
    languages: Mapped[list[str] | None] = mapped_column(CustomJSON(), default=[])
    tags: Mapped[list[str] | None] = mapped_column(CustomJSON(), default=[])

    crc_hash: Mapped[str | None] = mapped_column(String(length=100))
    md5_hash: Mapped[str | None] = mapped_column(String(length=100))
    sha1_hash: Mapped[str | None] = mapped_column(String(length=100))
    ra_hash: Mapped[str | None] = mapped_column(String(length=100))

    missing_from_fs: Mapped[bool] = mapped_column(default=False, nullable=False)

    platform_id: Mapped[int] = mapped_column(
        ForeignKey("platforms.id", ondelete="CASCADE")
    )

    platform: Mapped[Platform] = relationship(lazy="joined", back_populates="roms")
    sibling_roms: Mapped[list[Rom]] = relationship(
        secondary="sibling_roms",
        primaryjoin="Rom.id == SiblingRom.rom_id",
        secondaryjoin="Rom.id == SiblingRom.sibling_rom_id",
        lazy="raise",
    )
    files: Mapped[list[RomFile]] = relationship(lazy="raise", back_populates="rom")
    saves: Mapped[list[Save]] = relationship(lazy="raise", back_populates="rom")
    states: Mapped[list[State]] = relationship(lazy="raise", back_populates="rom")
    screenshots: Mapped[list[Screenshot]] = relationship(
        lazy="raise", back_populates="rom"
    )
    rom_users: Mapped[list[RomUser]] = relationship(lazy="raise", back_populates="rom")
    notes: Mapped[list[RomNote]] = relationship(lazy="raise", back_populates="rom")
    metadatum: Mapped[RomMetadata] = relationship(
        lazy="joined", back_populates="rom", uselist=False
    )
    collections: Mapped[list[Collection]] = relationship(
        "Collection",
        secondary="collections_roms",
        collection_class=set,
        lazy="raise",
        back_populates="roms",
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._is_identifying = False

    @property
    def platform_slug(self) -> str:
        return self.platform.slug

    @property
    def platform_fs_slug(self) -> str:
        return self.platform.fs_slug

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
        if self.path_screenshots:
            return [f"{FRONTEND_RESOURCES_PATH}/{s}" for s in self.path_screenshots]

        return []

    # TODO: Remove this after 4.3 release
    @cached_property
    def multi(self) -> bool:
        return self.has_nested_single_file or self.has_multiple_files

    @cached_property
    def has_simple_single_file(self) -> bool:
        return len(self.files) == 1 and not self.files[0].is_nested

    @cached_property
    def has_nested_single_file(self) -> bool:
        return len(self.files) == 1 and self.files[0].is_nested

    @cached_property
    def has_multiple_files(self) -> bool:
        return len(self.files) > 1

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

    @property
    def is_unidentified(self) -> bool:
        return (
            not self.igdb_id
            and not self.moby_id
            and not self.ss_id
            and not self.ra_id
            and not self.launchbox_id
            and not self.hasheous_id
            and not self.flashpoint_id
            and not self.hltb_id
            and not self.gamelist_id
        )

    @property
    def is_identified(self) -> bool:
        return not self.is_unidentified

    def has_m3u_file(self) -> bool:
        """
        Check if the ROM has an M3U file associated with it.
        This is used for multi-disc games.
        """
        return any(file.file_extension.lower() == "m3u" for file in self.files)

    # Metadata fields
    @property
    def youtube_video_id(self) -> str | None:
        igdb_video_id = (
            self.igdb_metadata.get("youtube_video_id", None)
            if self.igdb_metadata
            else None
        )
        lb_video_id = (
            self.launchbox_metadata.get("youtube_video_id", None)
            if self.launchbox_metadata
            else None
        )

        return igdb_video_id or lb_video_id

    @property
    def alternative_names(self) -> list[str]:
        return (
            (self.igdb_metadata or {}).get("alternative_names", None)
            or (self.moby_metadata or {}).get("alternate_titles", None)
            or (self.ss_metadata or {}).get("alternative_names", None)
            or []
        )

    @property
    def merged_ra_metadata(self) -> dict[str, list] | None:
        if self.ra_metadata and "achievements" in self.ra_metadata:
            for achievement in self.ra_metadata.get("achievements", []):
                achievement["badge_path_lock"] = (
                    f"{FRONTEND_RESOURCES_PATH}/{achievement['badge_path_lock']}"
                )
                achievement["badge_path"] = (
                    f"{FRONTEND_RESOURCES_PATH}/{achievement['badge_path']}"
                )
        return self.ra_metadata

    # Used only during scan process
    @property
    def is_identifying(self) -> bool:
        return self._is_identifying or False

    @is_identifying.setter
    def is_identifying(self, value: bool) -> None:
        self._is_identifying = value

    def __repr__(self) -> str:
        return f"{self.fs_name} ({self.id})"


class RomUserStatus(enum.StrEnum):
    INCOMPLETE = "incomplete"  # Started but not finished
    FINISHED = "finished"  # Reached the end of the game
    COMPLETED_100 = "completed_100"  # Completed 100%
    RETIRED = "retired"  # Won't play again
    NEVER_PLAYING = "never_playing"  # Will never play


class RomNote(BaseModel):
    __tablename__ = "rom_notes"
    __table_args__ = (
        UniqueConstraint(
            "rom_id", "user_id", "title", name="unique_rom_user_note_title"
        ),
        Index("idx_rom_notes_public", "is_public"),
        Index("idx_rom_notes_rom_user", "rom_id", "user_id"),
        Index("idx_rom_notes_title", "title"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Core note fields
    title: Mapped[str] = mapped_column(String(400))
    content: Mapped[str] = mapped_column(Text)
    is_public: Mapped[bool] = mapped_column(default=False)

    # Future extensibility fields
    tags: Mapped[list[str] | None] = mapped_column(CustomJSON(), default=list)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Foreign keys
    rom_id: Mapped[int] = mapped_column(ForeignKey("roms.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    # Relationships
    rom: Mapped[Rom] = relationship(lazy="joined", back_populates="notes")
    user: Mapped[User] = relationship(lazy="joined", back_populates="notes")

    @property
    def user__username(self) -> str:
        return self.user.username


class RomUser(BaseModel):
    __tablename__ = "rom_user"
    __table_args__ = (
        UniqueConstraint("rom_id", "user_id", name="unique_rom_user_props"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

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
