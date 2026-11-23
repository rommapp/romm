from __future__ import annotations

import json
from functools import cache, cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Final

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from handler.redis_handler import sync_cache
from models.base import (
    FILE_EXTENSION_MAX_LENGTH,
    FILE_NAME_MAX_LENGTH,
    FILE_PATH_MAX_LENGTH,
    BaseModel,
    FileNamePartsMixin,
)
from utils.arcade_platforms import ARCADE_PLATFORMS
from utils.platform_slugs import UniversalPlatformSlug as UPS

if TYPE_CHECKING:
    from models.platform import Platform

FIRMWARE_FIXTURES_DIR: Final = Path(__file__).parent / "fixtures"
KNOWN_BIOS_KEY = "romm:known_bios_files"
KNOWN_BIOS_FILE: Final = FIRMWARE_FIXTURES_DIR / "known_bios_files.json"

# The known BIOS list files every arcade BIOS, Neo Geo's included, under Arcade.
ARCADE_BIOS_PLATFORMS: Final = ARCADE_PLATFORMS | {UPS.NEOGEOAES, UPS.NEOGEOMVS}


@cache
def _known_bios_hashes() -> frozenset[tuple[int, str]]:
    """Index every known BIOS by (size, md5) and (size, sha1), whatever its name."""
    with KNOWN_BIOS_FILE.open() as f:
        known_bios: dict[str, dict[str, str]] = json.load(f)
    return frozenset(
        (int(entry["size"]), entry[algo].lower())
        for entry in known_bios.values()
        for algo in ("md5", "sha1")
        if entry.get(algo)
    )


class Firmware(FileNamePartsMixin, BaseModel):
    __tablename__ = "firmware"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform_id: Mapped[int] = mapped_column(
        ForeignKey("platforms.id", ondelete="CASCADE")
    )

    file_name: Mapped[str] = mapped_column(String(length=FILE_NAME_MAX_LENGTH))
    file_name_no_tags: Mapped[str] = mapped_column(String(length=FILE_NAME_MAX_LENGTH))
    file_name_no_ext: Mapped[str] = mapped_column(String(length=FILE_NAME_MAX_LENGTH))
    file_extension: Mapped[str] = mapped_column(
        String(length=FILE_EXTENSION_MAX_LENGTH)
    )
    file_path: Mapped[str] = mapped_column(String(length=FILE_PATH_MAX_LENGTH))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger(), default=0)

    crc_hash: Mapped[str] = mapped_column(String(length=100))
    md5_hash: Mapped[str] = mapped_column(String(length=100))
    sha1_hash: Mapped[str] = mapped_column(String(length=100))
    is_verified: Mapped[bool] = mapped_column(default=False, nullable=False)

    platform: Mapped[Platform] = relationship(lazy="joined", back_populates="firmware")

    missing_from_fs: Mapped[bool] = mapped_column(default=False, nullable=False)

    @cached_property
    def full_path(self) -> str:
        return f"{self.file_path}/{self.file_name}"

    @classmethod
    def verify_file_hashes(
        cls,
        platform_slug: str,
        file_name: str,
        file_size_bytes: int,
        md5_hash: str,
        sha1_hash: str,
        crc_hash: str,
    ) -> bool:
        bios_slug = (
            UPS.ARCADE if platform_slug in ARCADE_BIOS_PLATFORMS else platform_slug
        )
        cache_entry = sync_cache.hget(KNOWN_BIOS_KEY, f"{bios_slug}:{file_name}")
        if cache_entry:
            cache_json = json.loads(cache_entry)
            if file_size_bytes == int(cache_json.get("size", 0)) and (
                md5_hash == cache_json.get("md5")
                or sha1_hash == cache_json.get("sha1")
                or crc_hash == cache_json.get("crc")
            ):
                return True

        # A renamed or relocated dump still verifies by content. CRC32 is left
        # out here because without the name match it is too weak on its own.
        known_hashes = _known_bios_hashes()
        return any(
            bool(file_hash) and (file_size_bytes, file_hash.lower()) in known_hashes
            for file_hash in (md5_hash, sha1_hash)
        )

    def __repr__(self) -> str:
        return self.file_name
