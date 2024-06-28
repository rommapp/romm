from datetime import datetime

from pydantic import BaseModel, Field

from .firmware import FirmwareSchema


class PlatformSchema(BaseModel):
    id: int
    slug: str
    fs_slug: str
    name: str
    rom_count: int
    igdb_id: int | None = None
    sgdb_id: int | None = None
    moby_id: int | None = None
    logo_path: str | None = ""
    firmware: list[FirmwareSchema] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
