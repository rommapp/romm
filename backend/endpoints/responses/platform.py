from datetime import datetime

from models.platform import DEFAULT_COVER_ASPECT_RATIO
from pydantic import BaseModel, Field, computed_field

from .firmware import FirmwareSchema


class PlatformSchema(BaseModel):
    id: int
    slug: str
    fs_slug: str
    rom_count: int
    name: str
    custom_name: str | None = None
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
    aspect_ratio: str = DEFAULT_COVER_ASPECT_RATIO
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @computed_field  # type: ignore
    @property
    def display_name(self) -> str:
        return self.custom_name or self.name
