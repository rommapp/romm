from typing import Optional
from pydantic import BaseModel, Field
from fastapi import Request

from models.platform import Platform
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
    
    firmware: list[FirmwareSchema] = Field(default_factory=list)

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_request(cls, db_platform: Platform, request: Request) -> "PlatformSchema":
        platform = cls.model_validate(db_platform)
        platform.firmware = [
            FirmwareSchema.model_validate(f) for f in db_platform.firmware
        ]
        return platform
