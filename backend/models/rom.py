from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING, Any

from config import FRONTEND_RESOURCES_PATH
from models.base import BaseModel
from sqlalchemy import JSON, BigInteger, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql.json import JSON as MySQLJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from models.assets import Save, Screenshot, State
    from models.collection import Collection
    from models.platform import Platform
    from models.user import User


class Rom(BaseModel):
    __tablename__ = "roms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    igdb_id: Mapped[int | None]
    sgdb_id: Mapped[int | None]
    moby_id: Mapped[int | None]

    file_name: Mapped[str] = mapped_column(String(length=450))
    file_name_no_tags: Mapped[str] = mapped_column(String(length=450))
    file_name_no_ext: Mapped[str] = mapped_column(String(length=450))
    file_extension: Mapped[str] = mapped_column(String(length=100))
    file_path: Mapped[str] = mapped_column(String(length=1000))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger(), default=0)

    name: Mapped[str | None] = mapped_column(String(length=350))
    slug: Mapped[str | None] = mapped_column(String(length=400))
    summary: Mapped[str | None] = mapped_column(Text)
    igdb_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        MySQLJSON, default=dict
    )
    moby_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        MySQLJSON, default=dict
    )

    path_cover_s: Mapped[str | None] = mapped_column(Text, default="")
    path_cover_l: Mapped[str | None] = mapped_column(Text, default="")
    url_cover: Mapped[str | None] = mapped_column(
        Text, default="", doc="URL to cover image stored in IGDB"
    )

    revision: Mapped[str | None] = mapped_column(String(100))
    regions: Mapped[list[str] | None] = mapped_column(JSON, default=[])
    languages: Mapped[list[str] | None] = mapped_column(JSON, default=[])
    tags: Mapped[list[str] | None] = mapped_column(JSON, default=[])

    path_screenshots: Mapped[list[str] | None] = mapped_column(JSON, default=[])
    url_screenshots: Mapped[list[str] | None] = mapped_column(
        JSON, default=[], doc="URLs to screenshots stored in IGDB"
    )

    multi: Mapped[bool] = mapped_column(default=False)
    files: Mapped[list[str] | None] = mapped_column(JSON, default=[])

    platform_id: Mapped[int] = mapped_column(
        ForeignKey("platforms.id", ondelete="CASCADE")
    )

    platform: Mapped[Platform] = relationship(lazy="immediate")

    saves: Mapped[list[Save]] = relationship(back_populates="rom")
    states: Mapped[list[State]] = relationship(back_populates="rom")
    screenshots: Mapped[list[Screenshot]] = relationship(back_populates="rom")
    rom_users: Mapped[list[RomUser]] = relationship(back_populates="rom")

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
    def has_cover(self) -> bool:
        return bool(self.path_cover_s or self.path_cover_l)

    @cached_property
    def merged_screenshots(self) -> list[str]:
        return [s.download_path for s in self.screenshots] + [
            f"{FRONTEND_RESOURCES_PATH}/{s}" for s in self.path_screenshots
        ]

    # This is an expensive operation so don't call it on a list of roms
    def get_sibling_roms(self) -> list[Rom]:
        from handler.database import db_rom_handler

        return db_rom_handler.get_sibling_roms(self)

    def get_collections(self, user_id) -> list[Collection]:
        from handler.database import db_rom_handler

        return db_rom_handler.get_rom_collections(self, user_id)

    # Metadata fields
    @property
    def alternative_names(self) -> list[str]:
        return (
            self.igdb_metadata.get("alternative_names", None)
            or self.moby_metadata.get("alternate_titles", None)
            or []
        )

    @property
    def first_release_date(self) -> int:
        return self.igdb_metadata.get("first_release_date", 0)

    @property
    def genres(self) -> list[str]:
        return (
            self.igdb_metadata.get("genres", None)
            or self.moby_metadata.get("genres", None)
            or []
        )

    @property
    def franchises(self) -> list[str]:
        return self.igdb_metadata.get("franchises", [])

    @property
    def collections(self) -> list[str]:
        return self.igdb_metadata.get("collections", [])

    @property
    def companies(self) -> list[str]:
        return self.igdb_metadata.get("companies", [])

    @property
    def game_modes(self) -> list[str]:
        return self.igdb_metadata.get("game_modes", [])

    @property
    def fs_resources_path(self) -> str:
        return f"roms/{str(self.platform_id)}/{str(self.id)}"

    def __repr__(self) -> str:
        return self.file_name


class RomUser(BaseModel):
    __tablename__ = "rom_user"
    __table_args__ = (
        UniqueConstraint("rom_id", "user_id", name="unique_rom_user_props"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    note_raw_markdown: Mapped[str] = mapped_column(Text, default="")
    note_is_public: Mapped[bool] = mapped_column(default=False)

    is_main_sibling: Mapped[bool] = mapped_column(default=False)

    rom_id: Mapped[int] = mapped_column(ForeignKey("roms.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    rom: Mapped[Rom] = relationship(lazy="joined", back_populates="rom_users")
    user: Mapped[User] = relationship(lazy="joined", back_populates="rom_users")

    @property
    def user__username(self) -> str:
        return self.user.username
