from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from models.base import (
    FILE_EXTENSION_MAX_LENGTH,
    FILE_NAME_MAX_LENGTH,
    FILE_PATH_MAX_LENGTH,
    BaseModel,
    compute_file_name_parts,
)

if TYPE_CHECKING:
    from models.device_save_sync import DeviceSaveSync
    from models.platform import Platform
    from models.rom import Rom
    from models.user import User


class BaseAsset(BaseModel):
    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String(length=FILE_NAME_MAX_LENGTH))
    file_name_no_tags: Mapped[str] = mapped_column(String(length=FILE_NAME_MAX_LENGTH))
    file_name_no_ext: Mapped[str] = mapped_column(String(length=FILE_NAME_MAX_LENGTH))
    file_extension: Mapped[str] = mapped_column(
        String(length=FILE_EXTENSION_MAX_LENGTH)
    )
    file_path: Mapped[str] = mapped_column(String(length=FILE_PATH_MAX_LENGTH))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger(), default=0)

    missing_from_fs: Mapped[bool] = mapped_column(default=False, nullable=False)

    @validates("file_name")
    def _sync_file_name_parts(self, _key: str, file_name: str) -> str:
        """Derive the stored `file_name_no_tags` / `file_name_no_ext` /
        `file_extension` columns whenever `file_name` is assigned.

        Defined on the abstract base so every asset subclass inherits it.
        """
        parts = compute_file_name_parts(file_name)
        self.file_name_no_tags = parts.no_tags
        self.file_name_no_ext = parts.no_ext
        self.file_extension = parts.extension
        return file_name

    @cached_property
    def full_path(self) -> str:
        return f"{self.file_path}/{self.file_name}"

    @cached_property
    def download_path(self) -> str:
        # Served by the per-type `/{id}/content` route
        return (
            f"/api/{self.__tablename__}/{self.id}/content?timestamp={self.updated_at}"
        )


class RomAsset(BaseAsset):
    __abstract__ = True

    rom_id: Mapped[int] = mapped_column(ForeignKey("roms.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))


class Screenshot(RomAsset):
    __tablename__ = "screenshots"
    __table_args__ = {"extend_existing": True}

    # `is_gallery` distinguishes intentionally-uploaded gallery screenshots from
    # the auto-captured save/state thumbnails that also live in this table.
    # `is_public` mirrors RomNote — lets other users browse a user's public
    # screenshots (community). Both default false; save/state thumbnails keep the
    # defaults, only the gallery upload endpoint sets `is_gallery=True`.
    is_gallery: Mapped[bool] = mapped_column(default=False)
    is_public: Mapped[bool] = mapped_column(default=False)

    rom: Mapped[Rom] = relationship(lazy="joined", back_populates="screenshots")
    user: Mapped[User] = relationship(lazy="joined", back_populates="screenshots")


class Save(RomAsset):
    __tablename__ = "saves"
    __table_args__ = {"extend_existing": True}

    emulator: Mapped[str | None] = mapped_column(String(length=50))
    slot: Mapped[str | None] = mapped_column(String(length=255))
    content_hash: Mapped[str | None] = mapped_column(String(length=32))
    origin_device_id: Mapped[str | None] = mapped_column(
        String(length=255),
        ForeignKey("devices.id", ondelete="SET NULL"),
        default=None,
    )
    # `is_public` mirrors Screenshot/RomNote — lets other users browse and
    # download a user's public saves (community). Defaults false (private).
    is_public: Mapped[bool] = mapped_column(default=False)

    rom: Mapped[Rom] = relationship(lazy="joined", back_populates="saves")
    user: Mapped[User] = relationship(lazy="joined", back_populates="saves")
    device_syncs: Mapped[list[DeviceSaveSync]] = relationship(
        back_populates="save",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    @cached_property
    def screenshot(self) -> Screenshot | None:
        from handler.database import db_screenshot_handler

        return db_screenshot_handler.get_screenshot(
            rom_id=self.rom_id,
            user_id=self.user_id,
            file_name=self.file_name,  # Match state filename against screenshot filename stem
            file_name_no_ext=self.file_name_no_ext,
        )


class State(RomAsset):
    __tablename__ = "states"
    __table_args__ = {"extend_existing": True}

    emulator: Mapped[str | None] = mapped_column(String(length=50))
    # `is_public` mirrors Screenshot/RomNote — lets other users browse and
    # download a user's public states (community). Defaults false (private).
    is_public: Mapped[bool] = mapped_column(default=False)

    rom: Mapped[Rom] = relationship(lazy="joined", back_populates="states")
    user: Mapped[User] = relationship(lazy="joined", back_populates="states")

    @cached_property
    def screenshot(self) -> Screenshot | None:
        from handler.database import db_screenshot_handler

        return db_screenshot_handler.get_screenshot(
            rom_id=self.rom_id,
            user_id=self.user_id,
            file_name=self.file_name,  # Match state filename against screenshot filename stem
            file_name_no_ext=self.file_name_no_ext,
        )


class MemoryCard(BaseModel):
    """A per-user, per-emulator memory card that follows the user across
    streaming sessions. Unlike Save/State it is not tied to a single ROM: for
    formats like the PCSX2 folder card one card holds every game's saves. The
    card is an identity (name, owner); its actual data lives in `versions`,
    a snapshot history mirroring how EmulatorJS keeps multiple Save rows.
    """

    __tablename__ = "memory_cards"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # `emulator` is the hard scoping key: a card is looked up by (user, emulator)
    # at session claim, so one Dolphin card serves both GameCube and Wii roms.
    emulator: Mapped[str] = mapped_column(String(length=50))
    # `platform_id` is a loose, nullable hint (which platform the card was
    # created under) for display/filtering only. It never scopes the lookup, so
    # a card stays visible across every platform its emulator drives.
    platform_id: Mapped[int | None] = mapped_column(
        ForeignKey("platforms.id", ondelete="SET NULL"),
        default=None,
    )
    name: Mapped[str] = mapped_column(String(length=255))
    # Only slot 1 is used today; kept so a future multi-slot layout needs no
    # schema change.
    slot: Mapped[int] = mapped_column(default=1)
    # `is_public` mirrors Save/State, letting another user browse this card and
    # hydrate a snapshot of it. Sharing is one-way: the recipient's writes go
    # to their own new card, never back to this one.
    is_public: Mapped[bool] = mapped_column(default=False)

    user: Mapped[User] = relationship(lazy="joined", back_populates="memory_cards")
    # One-directional: the loose platform hint, for display only.
    platform: Mapped[Platform | None] = relationship(lazy="joined")
    versions: Mapped[list[MemoryCardVersion]] = relationship(
        back_populates="memory_card",
        cascade="all, delete-orphan",
        lazy="raise",
        order_by="MemoryCardVersion.created_at.desc()",
    )


class MemoryCardVersion(BaseAsset):
    """A single snapshot of a `MemoryCard`'s data (the whole card image, e.g.
    the zipped PCSX2 folder card). Multiple versions per card form its history.
    """

    __tablename__ = "memory_card_versions"
    __table_args__ = {"extend_existing": True}

    memory_card_id: Mapped[int] = mapped_column(
        ForeignKey("memory_cards.id", ondelete="CASCADE")
    )
    content_hash: Mapped[str | None] = mapped_column(String(length=32))

    memory_card: Mapped[MemoryCard] = relationship(
        lazy="joined", back_populates="versions"
    )

    @cached_property
    def download_path(self) -> str:
        # Served under the memory-cards router rather than the default
        # `/api/{tablename}/...`, keeping every card route in one namespace.
        return (
            f"/api/memory-cards/versions/{self.id}/content?timestamp={self.updated_at}"
        )
