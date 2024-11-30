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
    category: str | None = None
    generation: int | None = None
    family_name: str | None = None
    family_slug: str | None = None
    url: str | None = None
    url_logo: str | None = None
    logo_path: str | None = None
    firmware: list[FirmwareSchema] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
