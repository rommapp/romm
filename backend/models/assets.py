from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import (
    FILE_EXTENSION_MAX_LENGTH,
    FILE_NAME_MAX_LENGTH,
    FILE_PATH_MAX_LENGTH,
    BaseModel,
)

if TYPE_CHECKING:
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

    @cached_property
    def full_path(self) -> str:
        return f"{self.file_path}/{self.file_name}"

    @cached_property
    def download_path(self) -> str:
        return f"/api/raw/assets/{self.full_path}?timestamp={self.updated_at}"


class RomAsset(BaseAsset):
    __abstract__ = True

    rom_id: Mapped[int] = mapped_column(ForeignKey("roms.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))


class Save(RomAsset):
    __tablename__ = "saves"
    __table_args__ = {"extend_existing": True}

    emulator: Mapped[str | None] = mapped_column(String(length=50))

    rom: Mapped[Rom] = relationship(lazy="joined", back_populates="saves")
    user: Mapped[User] = relationship(lazy="joined", back_populates="saves")

    @cached_property
    def screenshot(self) -> Screenshot | None:
        from handler.database import db_screenshot_handler

        return db_screenshot_handler.get_screenshot(
            filename_no_ext=self.file_name_no_ext,
            rom_id=self.rom_id,
        )


class State(RomAsset):
    __tablename__ = "states"
    __table_args__ = {"extend_existing": True}

    emulator: Mapped[str | None] = mapped_column(String(length=50))

    rom: Mapped[Rom] = relationship(lazy="joined", back_populates="states")
    user: Mapped[User] = relationship(lazy="joined", back_populates="states")

    @cached_property
    def screenshot(self) -> Screenshot | None:
        from handler.database import db_screenshot_handler

        return db_screenshot_handler.get_screenshot(
            filename_no_ext=self.file_name_no_ext,
            rom_id=self.rom_id,
        )


class Screenshot(RomAsset):
    __tablename__ = "screenshots"
    __table_args__ = {"extend_existing": True}

    rom: Mapped[Rom] = relationship(lazy="joined", back_populates="screenshots")
    user: Mapped[User] = relationship(lazy="joined", back_populates="screenshots")
