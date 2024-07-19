from __future__ import annotations

import json
import os
from functools import cached_property
from typing import TYPE_CHECKING

from handler.metadata.base_hander import conditionally_set_cache
from handler.redis_handler import cache
from models.base import BaseModel
from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from models.platform import Platform

KNOWN_BIOS_KEY = "romm:known_bios_files"
conditionally_set_cache(
    KNOWN_BIOS_KEY, "known_bios_files.json", os.path.dirname(__file__)
)


class Firmware(BaseModel):
    __tablename__ = "firmware"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform_id: Mapped[int] = mapped_column(
        ForeignKey("platforms.id", ondelete="CASCADE")
    )

    file_name: Mapped[str] = mapped_column(String(length=450))
    file_name_no_tags: Mapped[str] = mapped_column(String(length=450))
    file_name_no_ext: Mapped[str] = mapped_column(String(length=450))
    file_extension: Mapped[str] = mapped_column(String(length=100))
    file_path: Mapped[str] = mapped_column(String(length=1000))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger(), default=0)

    crc_hash: Mapped[str] = mapped_column(String(length=100))
    md5_hash: Mapped[str] = mapped_column(String(length=100))
    sha1_hash: Mapped[str] = mapped_column(String(length=100))

    platform: Mapped[Platform] = relationship(lazy="joined", back_populates="firmware")

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
    def is_verified(self) -> bool:
        cache_entry = cache.hget(
            KNOWN_BIOS_KEY, f"{self.platform_slug}:{self.file_name}"
        )
        if cache_entry:
            cache_json = json.loads(cache_entry)
            return (
                self.file_size_bytes == int(cache_json.get("size", 0))
                and self.md5_hash == cache_json.get("md5")
                and self.sha1_hash == cache_json.get("sha1")
                and self.crc_hash == cache_json.get("crc")
            )

        return False

    @cached_property
    def full_path(self) -> str:
        return f"{self.file_path}/{self.file_name}"

    def __repr__(self) -> str:
        return self.file_name
