import os
import json
from functools import cached_property
from sqlalchemy.orm import relationship
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    BigInteger,
)

from models.base import BaseModel
from handler.redis_handler import cache
from handler.metadata.base_metadata_hander import conditionally_set_cache

KNOWN_BIOS_KEY = "romm:known_bios_files"
conditionally_set_cache(
    KNOWN_BIOS_KEY, "known_bios_files.json", os.path.dirname(__file__)
)


class Firmware(BaseModel):
    __tablename__ = "firmware"

    id = Column(Integer(), primary_key=True, autoincrement=True)
    platform_id = Column(
        Integer(), ForeignKey("platforms.id", ondelete="CASCADE"), nullable=False
    )

    file_name = Column(String(length=450), nullable=False)
    file_name_no_tags = Column(String(length=450), nullable=False)
    file_name_no_ext = Column(String(length=450), nullable=False)
    file_extension = Column(String(length=100), nullable=False)
    file_path = Column(String(length=1000), nullable=False)
    file_size_bytes = Column(BigInteger(), default=0, nullable=False)

    crc_hash = Column(String(length=100), nullable=False)
    md5_hash = Column(String(length=100), nullable=False)
    sha1_hash = Column(String(length=100), nullable=False)

    platform = relationship("Platform", lazy="joined", back_populates="firmware")

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
