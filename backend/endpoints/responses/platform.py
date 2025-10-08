from datetime import datetime

from pydantic import Field, computed_field, field_validator

from models.platform import DEFAULT_COVER_ASPECT_RATIO

from .base import BaseModel
from .firmware import FirmwareSchema


class PlatformSchema(BaseModel):
    id: int
    slug: str
    fs_slug: str
    rom_count: int
    name: str
    igdb_slug: str | None
    moby_slug: str | None
    hltb_slug: str | None
    custom_name: str | None = None
    igdb_id: int | None = None
    sgdb_id: int | None = None
    moby_id: int | None = None
    launchbox_id: int | None = None
    ss_id: int | None = None
    ra_id: int | None = None
    hasheous_id: int | None = None
    tgdb_id: int | None = None
    flashpoint_id: int | None = None
    category: str | None = None
    generation: int | None = None
    family_name: str | None = None
    family_slug: str | None = None
    url: str | None = None
    url_logo: str | None = None
    firmware: list[FirmwareSchema] = Field(default_factory=list)
    aspect_ratio: str = DEFAULT_COVER_ASPECT_RATIO
    created_at: datetime
    updated_at: datetime
    fs_size_bytes: int
    is_unidentified: bool
    is_identified: bool
    missing_from_fs: bool

    class Config:
        from_attributes = True

    @computed_field  # type: ignore
    @property
    def display_name(self) -> str:
        return self.custom_name or self.name

    @field_validator("firmware")
    def sort_files(cls, v: list[FirmwareSchema]) -> list[FirmwareSchema]:
        return sorted(v, key=lambda x: x.file_name)
