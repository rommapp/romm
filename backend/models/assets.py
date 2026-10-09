from __future__ import annotations

import enum
import uuid
from functools import cached_property
from typing import TYPE_CHECKING, NamedTuple
from urllib.parse import quote

from sqlalchemy import BigInteger, Enum, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import (
    FILE_EXTENSION_MAX_LENGTH,
    FILE_NAME_MAX_LENGTH,
    FILE_PATH_MAX_LENGTH,
    BaseModel,
    FileNamePartsMixin,
    compute_file_extension,
)
from utils.database import CustomJSON, ExactString

if TYPE_CHECKING:
    from models.device_save_sync import DeviceSaveSync
    from models.platform import Platform
    from models.rom import Rom
    from models.user import User


SAVE_SLOT_MAX_LENGTH = 255
# Where a client with no slot of its own files new progress.
AUTOSAVE_SLOT = "autosave"
# A slot's versions, newest last: pruning locks exactly these rows through it.
SAVE_SLOT_VERSIONS_INDEX = "ix_saves_rom_user_slot_updated"
EMULATOR_MAX_LENGTH = 50
MEMORY_CARD_NAME_MAX_LENGTH = 255
ASSET_LABEL_MAX_LENGTH = 255
ASSET_LABELS_MAX = 20
CONTENT_HASH_MAX_LENGTH = 32
EMULATOR_VERSION_MAX_LENGTH = 100


class SaveShape(enum.StrEnum):
    """How a save unit travels, as sigil packs it."""

    SINGLE = "SINGLE"
    MULTI = "MULTI"
    FOLDER = "FOLDER"


class SaveFormat(enum.StrEnum):
    NEUTRAL = "neutral"
    NATIVE = "native"


class SaveLineage(NamedTuple):
    """One emulator's saves in one format, whose versions in a slot are pruned together."""

    emulator: str | None
    file_extension: str

    @classmethod
    def of(cls, emulator: str | None, file_name: str) -> SaveLineage:
        return cls(emulator, compute_file_extension(file_name).lower())


class BaseAsset(FileNamePartsMixin, BaseModel):
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

    @cached_property
    def full_path(self) -> str:
        return f"{self.file_path}/{self.file_name}"

    @cached_property
    def download_path(self) -> str:
        # Served by the per-type `/{id}/content` route. A rename keeps
        # `updated_at`, so the name joins the cache key.
        return (
            f"/api/{self.__tablename__}/{self.id}/content"
            f"?timestamp={self.updated_at}&name={quote(self.file_name)}"
        )


class RomAsset(BaseAsset):
    __abstract__ = True

    rom_id: Mapped[int] = mapped_column(ForeignKey("roms.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))


class DetachedContentError(LookupError):
    """A save or state whose ROM was deleted reached a flow that needs the ROM."""

    def __init__(self, asset: "ChannelContent"):
        super().__init__(f"{asset.file_name} has no ROM")


class ChannelContent(RomAsset):
    """A save or state that sync files under a channel. Null is a backup the user manages."""

    __abstract__ = True

    # Deleting the ROM detaches the row; a rescan with the same file key reattaches it.
    rom_id: Mapped[int | None] = mapped_column(  # type: ignore[assignment]
        ForeignKey("roms.id", ondelete="SET NULL")
    )

    if TYPE_CHECKING:
        rom: Mapped[Rom | None]

    @property
    def attached_rom(self) -> Rom:
        """The ROM, for legacy flows, whose queries never load a detached row."""
        if self.rom is None:
            raise DetachedContentError(self)
        return self.rom

    @property
    def attached_rom_id(self) -> int:
        if self.rom_id is None:
            raise DetachedContentError(self)
        return self.rom_id

    channel_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("channels.id", ondelete="SET NULL"), default=None
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(length=CONTENT_HASH_MAX_LENGTH), default=None
    )


class Screenshot(RomAsset):
    __tablename__ = "screenshots"
    __table_args__ = (
        # `Save.screenshot` / `State.screenshot` hit this once per rendered card.
        Index("ix_screenshots_rom_user", "rom_id", "user_id"),
        Index("idx_screenshots_public", "is_public"),
        Index("ix_screenshots_save_id", "save_id", unique=True),
        Index("ix_screenshots_state_id", "state_id", unique=True),
        {"extend_existing": True},
    )

    # `is_gallery` distinguishes intentionally-uploaded gallery screenshots from
    # the auto-captured save/state thumbnails that also live in this table.
    # `is_public` mirrors RomNote: it lets other users browse a user's public
    # screenshots (community). Both default false; save/state thumbnails keep the
    # defaults, only the gallery upload endpoint sets `is_gallery=True`.
    is_gallery: Mapped[bool] = mapped_column(default=False)
    is_public: Mapped[bool] = mapped_column(default=False)
    # The content row a thumbnail belongs to; both null on a gallery screenshot.
    save_id: Mapped[int | None] = mapped_column(
        ForeignKey("saves.id", ondelete="CASCADE"), default=None
    )
    state_id: Mapped[int | None] = mapped_column(
        ForeignKey("states.id", ondelete="CASCADE"), default=None
    )

    rom: Mapped[Rom] = relationship(lazy="joined", back_populates="screenshots")
    user: Mapped[User] = relationship(lazy="joined", back_populates="screenshots")


class Save(ChannelContent):
    __tablename__ = "saves"
    __table_args__ = (
        Index("ix_saves_rom_user_hash", "rom_id", "user_id", "content_hash"),
        Index("idx_saves_public", "is_public"),
        Index(SAVE_SLOT_VERSIONS_INDEX, "rom_id", "user_id", "slot", "updated_at"),
        Index("ix_saves_channel_updated", "channel_id", "updated_at"),
        {"extend_existing": True},
    )

    emulator: Mapped[str | None] = mapped_column(String(length=EMULATOR_MAX_LENGTH))
    # Exact, so the database pairs slots as sync negotiation does in Python.
    slot: Mapped[str | None] = mapped_column(
        ExactString(SAVE_SLOT_MAX_LENGTH), index=True
    )
    # `content_hash` without the clock member, so a clock tick alone reads as no change.
    identity_hash: Mapped[str | None] = mapped_column(
        String(length=CONTENT_HASH_MAX_LENGTH), default=None
    )
    shape: Mapped[SaveShape | None] = mapped_column(Enum(SaveShape), default=None)
    format: Mapped[SaveFormat | None] = mapped_column(Enum(SaveFormat), default=None)
    emulator_version: Mapped[str | None] = mapped_column(
        String(length=EMULATOR_VERSION_MAX_LENGTH), default=None
    )
    # The libretro core that wrote the save; NULL for a standalone emulator or when unreported.
    core: Mapped[str | None] = mapped_column(
        String(length=EMULATOR_MAX_LENGTH), default=None
    )
    core_version: Mapped[str | None] = mapped_column(
        String(length=EMULATOR_VERSION_MAX_LENGTH), default=None
    )
    origin_device_id: Mapped[str | None] = mapped_column(
        String(length=255),
        ForeignKey("devices.id", ondelete="SET NULL"),
        default=None,
        index=True,
    )
    # `is_public` mirrors Screenshot/RomNote: it lets other users browse and
    # download a user's public saves (community). Defaults false (private).
    is_public: Mapped[bool] = mapped_column(default=False)
    # Owner-only annotations: favorites sort ahead of the rest, labels tell
    # apart runs a filename and a timestamp cannot (a route, a seed, a run).
    is_favorite: Mapped[bool] = mapped_column(default=False)
    labels: Mapped[list[str] | None] = mapped_column(CustomJSON(), default=[])

    rom: Mapped[Rom | None] = relationship(lazy="joined", back_populates="saves")
    user: Mapped[User] = relationship(lazy="joined", back_populates="saves")
    device_syncs: Mapped[list[DeviceSaveSync]] = relationship(
        back_populates="save",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    @property
    def lineage(self) -> SaveLineage:
        return SaveLineage.of(self.emulator, self.file_name)

    @cached_property
    def screenshot(self) -> Screenshot | None:
        from handler.database import db_screenshot_handler

        if self.rom_id is None:
            return None
        return db_screenshot_handler.get_screenshot(
            rom_id=self.rom_id,
            user_id=self.user_id,
            file_name=self.file_name,  # Match state filename against screenshot filename stem
            file_name_no_ext=self.file_name_no_ext,
        )


class State(ChannelContent):
    __tablename__ = "states"
    __table_args__ = (
        Index("ix_states_rom_user", "rom_id", "user_id"),
        Index("idx_states_public", "is_public"),
        Index("ix_states_channel_id", "channel_id"),
        {"extend_existing": True},
    )

    emulator: Mapped[str | None] = mapped_column(String(length=EMULATOR_MAX_LENGTH))
    # `is_public` mirrors Screenshot/RomNote: it lets other users browse and
    # download a user's public states (community). Defaults false (private).
    is_public: Mapped[bool] = mapped_column(default=False)
    # Owner-only annotations: favorites sort ahead of the rest, labels tell
    # apart runs a filename and a timestamp cannot (a route, a seed, a run).
    is_favorite: Mapped[bool] = mapped_column(default=False)
    labels: Mapped[list[str] | None] = mapped_column(CustomJSON(), default=[])
    # The disc mounted when this state was captured, so a resume can put the
    # same one back. SET NULL rather than CASCADE: losing the file row must
    # not take the player's save with it.
    disc_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("rom_files.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        index=True,
    )
    # The libretro core that wrote this RetroArch state. NULL is the platform's
    # default core, which wrote every state stored before cores were recorded.
    core: Mapped[str | None] = mapped_column(
        String(length=EMULATOR_MAX_LENGTH), nullable=True, default=None
    )
    emulator_version: Mapped[str | None] = mapped_column(
        String(length=EMULATOR_VERSION_MAX_LENGTH), default=None
    )
    core_version: Mapped[str | None] = mapped_column(
        String(length=EMULATOR_VERSION_MAX_LENGTH), default=None
    )

    rom: Mapped[Rom | None] = relationship(lazy="joined", back_populates="states")
    user: Mapped[User] = relationship(lazy="joined", back_populates="states")

    @cached_property
    def screenshot(self) -> Screenshot | None:
        from handler.database import db_screenshot_handler

        if self.rom_id is None:
            return None
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
    __table_args__ = (
        Index("ix_memory_cards_user_emulator", "user_id", "emulator"),
        Index("ix_memory_cards_public", "is_public"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # `emulator` is the hard scoping key: a card is looked up by (user, emulator)
    # at session claim, so one Dolphin card serves both GameCube and Wii roms.
    emulator: Mapped[str] = mapped_column(String(length=EMULATOR_MAX_LENGTH))
    # `platform_id` is a loose, nullable hint (which platform the card was
    # created under) for display/filtering only. It never scopes the lookup, so
    # a card stays visible across every platform its emulator drives.
    platform_id: Mapped[int | None] = mapped_column(
        ForeignKey("platforms.id", ondelete="SET NULL"),
        default=None,
    )
    name: Mapped[str] = mapped_column(String(length=MEMORY_CARD_NAME_MAX_LENGTH))
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
    __table_args__ = (
        Index("ix_memory_card_versions_card_hash", "memory_card_id", "content_hash"),
        {"extend_existing": True},
    )

    memory_card_id: Mapped[int] = mapped_column(
        ForeignKey("memory_cards.id", ondelete="CASCADE")
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(length=CONTENT_HASH_MAX_LENGTH)
    )

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
