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
    """The internal ID of the platform."""
    slug: str
    """The canonical slug, such as `snes`."""
    fs_slug: str
    """The name of the platform's folder in the library."""
    rom_count: int
    """The number of roms on the platform that the caller can see."""
    name: str
    """The name of the platform."""
    igdb_slug: str | None
    """The IGDB slug of the platform."""
    moby_slug: str | None
    """The MobyGames slug of the platform."""
    hltb_slug: str | None
    """The HowLongToBeat slug of the platform."""
    libretro_slug: str | None
    """The Libretro slug of the platform."""
    custom_name: str | None = None
    """The name the user gave the platform in place of its own."""
    description: str | None = None
    """The description of the platform."""
    igdb_id: int | None = None
    """The IGDB ID of the platform."""
    sgdb_id: int | None = None
    """The SteamGridDB ID of the platform, used to find artwork."""
    moby_id: int | None = None
    """The MobyGames ID of the platform."""
    launchbox_id: int | None = None
    """The LaunchBox ID of the platform."""
    ss_id: int | None = None
    """The ScreenScraper ID of the platform."""
    ra_id: int | None = None
    """The RetroAchievements ID of the platform."""
    hasheous_id: int | None = None
    """The Hasheous ID of the platform."""
    tgdb_id: int | None = None
    """The TheGamesDB ID of the platform."""
    flashpoint_id: int | None = None
    """The Flashpoint Project ID of the platform."""
    category: str | None = None
    """The category of the platform."""
    generation: int | None = None
    """The hardware generation of the platform."""
    first_release_year: int | None = None
    """The year the platform was first released."""
    family_name: str | None = None
    """The name of the platform family."""
    family_slug: str | None = None
    """The slug of the platform family."""
    url: str | None = None
    """The URL of a web page about the platform."""
    url_logo: str | None = None
    """The URL of the platform's logo."""
    firmware: list[FirmwareSchema] = Field(default_factory=list)
    """The platform's firmware files, such as BIOS images."""
    created_at: UTCDatetime
    """When the platform was added to the library."""
    updated_at: UTCDatetime
    """When the platform's record last changed."""
    fs_size_bytes: int
    """The total size of the platform's roms on disk, in bytes."""
    is_unidentified: bool
    """True when no provider has matched the platform."""
    is_identified: bool
    """True when at least one provider has matched the platform."""
    missing_from_fs: bool
    """True when the platform's folder is no longer in the library."""

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
        """The number of firmware files, usable or not."""
        return len(self.firmware)

    @field_validator("firmware")
    def sort_files(cls, v: list[FirmwareSchema]) -> list[FirmwareSchema]:
        return sorted(v, key=lambda x: x.file_name)
