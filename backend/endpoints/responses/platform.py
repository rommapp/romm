from pydantic import ConfigDict, Field, computed_field, field_validator

from handler.metadata.platform_names import (
    platform_abbreviation,
    platform_alternative_names,
)

from .base import BaseModel, UTCDatetime
from .firmware import FirmwareSchema


class PlatformSchema(BaseModel):
    """A platform: a console, handheld or other system with roms in the library."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    """The canonical slug, such as `snes`."""
    fs_slug: str
    """The name of the platform's folder in the library."""
    rom_count: int
    """The number of roms on the platform that the caller can see."""
    name: str
    igdb_slug: str | None
    moby_slug: str | None
    hltb_slug: str | None
    libretro_slug: str | None
    custom_name: str | None = None
    """A custom name the user set for the platform."""
    description: str | None = None
    igdb_id: int | None = None
    sgdb_id: int | None = None
    """The SteamGridDB ID of the platform, used to find artwork."""
    moby_id: int | None = None
    launchbox_id: int | None = None
    ss_id: int | None = None
    ra_id: int | None = None
    hasheous_id: int | None = None
    tgdb_id: int | None = None
    flashpoint_id: int | None = None
    category: str | None = None
    generation: int | None = None
    first_release_year: int | None = None
    family_name: str | None = None
    family_slug: str | None = None
    url: str | None = None
    """The URL of a web page about the platform."""
    url_logo: str | None = None
    firmware: list[FirmwareSchema] = Field(default_factory=list)
    created_at: UTCDatetime
    updated_at: UTCDatetime
    fs_size_bytes: int
    """The total size of the platform's roms on disk, in bytes."""
    is_unidentified: bool
    """True when no provider has matched the platform."""
    is_identified: bool
    """True when at least one provider has matched the platform."""
    missing_from_fs: bool

    @computed_field  # type: ignore[prop-decorator]
    @property
    def display_name(self) -> str:
        """The custom name when set, otherwise the platform's name."""
        return self.custom_name or self.name

    @computed_field  # type: ignore[prop-decorator]
    @property
    def abbreviation(self) -> str:
        """The short name of the platform."""
        return platform_abbreviation(self.slug)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def alternative_names(self) -> list[str]:
        """Other names the platform is known by."""
        return list(platform_alternative_names(self.slug))

    # Counts every row like `rom_count` does; callers wanting only usable
    # BIOS filter the `firmware` list that ships alongside it.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def firmware_count(self) -> int:
        """The number of firmware files, whether usable or not."""
        return len(self.firmware)

    @field_validator("firmware")
    def sort_files(cls, v: list[FirmwareSchema]) -> list[FirmwareSchema]:
        return sorted(v, key=lambda x: x.file_name)
