from typing import Optional
from pydantic import BaseModel, Field

from .firmware import FirmwareSchema


class PlatformSchema(BaseModel):
    id: int
    slug: str
    fs_slug: str
    name: str
    rom_count: int
    igdb_id: Optional[int] = None
    sgdb_id: Optional[int] = None
    moby_id: Optional[int] = None
    logo_path: Optional[str] = ""
    firmware: list[FirmwareSchema] = Field(default_factory=list)

    class Config:
        from_attributes = True
