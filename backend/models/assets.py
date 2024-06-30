from functools import cached_property
from typing import TYPE_CHECKING, Optional

from models.base import BaseModel
from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from models.rom import Rom
    from models.user import User


class BaseAsset(BaseModel):
    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String(length=450))
    file_name_no_tags: Mapped[str] = mapped_column(String(length=450))
    file_name_no_ext: Mapped[str] = mapped_column(String(length=450))
    file_extension: Mapped[str] = mapped_column(String(length=100))
    file_path: Mapped[str] = mapped_column(String(length=1000))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger(), default=0)

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

    rom: Mapped["Rom"] = relationship(lazy="joined", back_populates="saves")
    user: Mapped["User"] = relationship(lazy="joined", back_populates="saves")

    @cached_property
    def screenshot(self) -> Optional["Screenshot"]:
        from handler.database import db_rom_handler

        db_rom = db_rom_handler.get_rom(self.rom_id)
        if db_rom is None:
            return None

        for screenshot in db_rom.screenshots:
            if screenshot.file_name_no_ext == self.file_name:
                return screenshot

        return None


class State(RomAsset):
    __tablename__ = "states"
    __table_args__ = {"extend_existing": True}

    emulator: Mapped[str | None] = mapped_column(String(length=50))

    rom: Mapped["Rom"] = relationship(lazy="joined", back_populates="states")
    user: Mapped["User"] = relationship(lazy="joined", back_populates="states")

    @cached_property
    def screenshot(self) -> Optional["Screenshot"]:
        from handler.database import db_rom_handler

        db_rom = db_rom_handler.get_rom(self.rom_id)
        if db_rom is None:
            return None

        for screenshot in db_rom.screenshots:
            if screenshot.file_name_no_ext == self.file_name:
                return screenshot

        return None


class Screenshot(RomAsset):
    __tablename__ = "screenshots"
    __table_args__ = {"extend_existing": True}

    rom: Mapped["Rom"] = relationship(lazy="joined", back_populates="screenshots")
    user: Mapped["User"] = relationship(lazy="joined", back_populates="screenshots")
