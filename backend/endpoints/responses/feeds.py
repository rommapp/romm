from datetime import datetime
from typing import Annotated, Any, Final, NotRequired, TypedDict

from pydantic import BaseModel, BeforeValidator, Field, field_validator

from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from tasks.scheduled.update_switch_titledb import TITLEDB_REGION_LIST
from utils.database import safe_int

WEBRCADE_SUPPORTED_PLATFORM_SLUGS = frozenset(
    (
        UPS._3DO,
        UPS.ARCADE,
        UPS.ATARI2600,
        UPS.ATARI5200,
        UPS.ATARI7800,
        UPS.C64,
        UPS.COLECOVISION,
        UPS.DOS,
        UPS.GAMEGEAR,
        UPS.GB,
        UPS.GBA,
        UPS.GBC,
        UPS.GENESIS,
        UPS.LYNX,
        UPS.N64,
        UPS.NEO_GEO_CD,
        UPS.NEO_GEO_POCKET,
        UPS.NEO_GEO_POCKET_COLOR,
        UPS.NEOGEOAES,
        UPS.NEOGEOMVS,
        UPS.NES,
        UPS.PC_FX,
        UPS.PSX,
        UPS.SEGACD,
        UPS.SG1000,
        UPS.SMS,
        UPS.SNES,
        UPS.SUPERGRAFX,
        UPS.TURBOGRAFX_CD,
        UPS.TG16,
        UPS.VIRTUALBOY,
        UPS.WONDERSWAN,
        UPS.WONDERSWAN_COLOR,
    )
)

WEBRCADE_SLUG_TO_TYPE_MAP = {
    UPS.ATARI2600: "2600",
    UPS.ATARI5200: "5200",
    UPS.ATARI7800: "7800",
    UPS.C64: "commodore-c64",
    UPS.LYNX: "lnx",
    UPS.TG16: "pce",
    UPS.TURBOGRAFX_CD: "pce",
    UPS.SUPERGRAFX: "sgx",
    UPS.PC_FX: "pcfx",
    UPS.VIRTUALBOY: "vb",
    UPS.GAMEGEAR: "gg",
    UPS.NEOGEOAES: "neogeo",
    UPS.NEOGEOMVS: "neogeo",
    UPS.NEO_GEO_CD: "neogeocd",
    UPS.NEO_GEO_POCKET: "ngp",
    UPS.NEO_GEO_POCKET_COLOR: "ngc",
}


# Webrcade feed format
# Source: https://docs.webrcade.com/feeds/format/
class WebrcadeFeedItemPropsSchema(TypedDict):
    rom: str


class WebrcadeFeedItemSchema(TypedDict):
    title: str
    longTitle: NotRequired[str]
    description: NotRequired[str]
    type: str
    thumbnail: NotRequired[str]
    background: NotRequired[str]
    props: WebrcadeFeedItemPropsSchema


class WebrcadeFeedCategorySchema(TypedDict):
    title: str
    longTitle: NotRequired[str]
    background: NotRequired[str]
    thumbnail: NotRequired[str]
    description: NotRequired[str]
    items: list[WebrcadeFeedItemSchema]


class WebrcadeFeedSchema(TypedDict):
    title: str
    longTitle: NotRequired[str]
    description: NotRequired[str]
    thumbnail: NotRequired[str]
    background: NotRequired[str]
    categories: list[WebrcadeFeedCategorySchema]


# Tinfoil feed format
# Source: https://blawar.github.io/tinfoil/custom_index/

UNIX_EPOCH_START_DATE: Final = 19700101


def coerce_to_string(value: Any) -> str:
    """Coerce value to string, returning empty string for None."""
    return "" if value is None else str(value)


def coerce_to_int(value: Any) -> int:
    """Coerce value to int, returning 0 for None/empty values."""
    return safe_int(value, default=0)


# Annotated types for cleaner field definitions
StringField = Annotated[str, BeforeValidator(coerce_to_string)]
IntField = Annotated[int, BeforeValidator(coerce_to_int)]


class TinfoilFeedFileSchema(TypedDict):
    url: str
    size: int


class TinfoilFeedTitleDBSchema(BaseModel):
    """Schema for Tinfoil feed title database entries.

    This schema handles the conversion and validation of game metadata
    for the Tinfoil custom index format.
    """

    id: StringField = Field(default="")
    name: StringField = Field(default="")
    description: StringField = Field(default="")
    region: StringField = Field(default="US")
    publisher: StringField = Field(default="")
    releaseDate: IntField = Field(default=UNIX_EPOCH_START_DATE)
    size: IntField = Field(default=0, ge=0)
    version: IntField = Field(default=0, ge=0)
    rating: IntField = Field(default=0, ge=0, le=100)
    rank: IntField = Field(default=0, ge=0)

    @field_validator("region")
    def validate_region(cls, v: str) -> str:
        if v not in TITLEDB_REGION_LIST:
            return "US"
        return v

    @field_validator("releaseDate")
    def validate_release_date(cls, v: int) -> int:
        if v < UNIX_EPOCH_START_DATE:
            return UNIX_EPOCH_START_DATE
        return v


class TinfoilFeedSchema(TypedDict):
    files: list[TinfoilFeedFileSchema]
    directories: list[str]
    titledb: NotRequired[dict[str, dict]]  # dict after .model_dump()
    success: NotRequired[str]
    error: NotRequired[str]


# PKGi PS3 feed format
# Source: https://github.com/bucanero/pkgi-ps3
class PKGiFeedPS3ItemSchema(BaseModel):
    """Schema for PKGi PS3 feed items.

    Follows the PKGi database format:
    contentid,type,name,description,rap,url,size,checksum
    """

    contentid: str
    type: int
    name: str
    description: str
    rap: str
    url: str
    size: int
    checksum: str


# PKGi PSP feed format
# Source: https://github.com/bucanero/pkgi-psp
class PKGiFeedPSPItemSchema(PKGiFeedPS3ItemSchema):
    """Schema for PKGi PSP feed items.

    Follows the PKGi database format:
    contentid,type,name,description,rap,url,size,checksum
    """

    pass


# PKGi PS Vita feed format
# Source: https://github.com/mmozeiko/pkgi
class PKGiFeedPSVitaItemSchema(BaseModel):
    """Schema for PKGi PS Vita feed items.

    Follows the PKGi database format:
    contentid,flags,name,name2,zrif,url,size,checksum
    """

    contentid: str
    flags: int
    name: str
    name2: str
    zrif: str
    url: str
    size: int
    checksum: str


# FPKGi feed format
# Source: https://github.com/ItsJokerZz/FPKGi
class FPKGiFeedItemSchema(BaseModel):
    name: str
    size: int
    title_id: str
    region: str | None
    version: str | None
    release: str | None
    min_fw: str | None
    cover_url: str | None


# Kekatsu DS feed format
# Source: https://github.com/cavv-dev/Kekatsu-DS
class KekatsuDSItemSchema(BaseModel):
    """Schema for Kekatsu DS feed items.

    Follows the Kekatsu DS database format:
    title,platform,region,version,author,download_url,filename,size,box_art_url[,extract_items...]
    """

    title: str
    platform: str
    region: str
    version: str
    author: str
    download_url: str
    filename: str
    size: int
    box_art_url: str


# Pkgj feed formats
# Source: https://github.com/rommapp/romm/issues/2899
class PkgjBaseItemSchema(BaseModel):
    title_id: str
    region: str
    name: str
    download_link: str
    content_id: str
    last_modified: datetime
    file_size: int
    sha_256: str


class PkgjPSPGamesItemSchema(PkgjBaseItemSchema):
    type: str
    rap: str
    download_rap_file: str


class PkgjPSPDlcsItemSchema(PkgjBaseItemSchema):
    rap: str
    download_rap_file: str


class PkgjPSVGamesItemSchema(PkgjBaseItemSchema):
    zrif: str
    original_name: str
    required_fw: str
    app_version: str


class PkgjPSVDlcsItemSchema(PkgjBaseItemSchema):
    zrif: str


class PkgjPSXGamesItemSchema(PkgjBaseItemSchema):
    original_name: str
