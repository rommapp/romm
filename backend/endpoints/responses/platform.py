from typing import Optional

from fastapi import Request
from models.platform import Platform
from pydantic import BaseModel, Field

from .firmware import FirmwareSchema


class PlatformSchema(BaseModel):
    id: int
    slug: str
    fs_slug: str
    igdb_id: Optional[int] = None
    sgdb_id: Optional[int] = None
    moby_id: Optional[int] = None
    name: str
    logo_path: Optional[str] = ""
    rom_count: int

    firmware_files: list[FirmwareSchema] = Field(default_factory=list)

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_request(
        cls, db_platform: Platform, request: Request
    ) -> "PlatformSchema":
        platform = cls.model_validate(db_platform)
        platform.firmware_files = [
            FirmwareSchema.model_validate(f)
            for f in sorted(db_platform.firmware, key=lambda x: x.file_name)
        ]
        return platform
