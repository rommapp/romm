from typing import NotRequired, TypedDict

from handler.metadata.base_handler import UniversalPlatformSlug as UPS

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


class TinfoilFeedFileSchema(TypedDict):
    url: str
    size: int


class TinfoilFeedTitleDBSchema(TypedDict):
    id: str
    name: str
    version: int
    region: str
    releaseDate: int
    rating: int
    publisher: str
    description: str
    size: int
    rank: int


class TinfoilFeedSchema(TypedDict):
    files: list[TinfoilFeedFileSchema]
    directories: list[str]
    titledb: NotRequired[dict[str, TinfoilFeedTitleDBSchema]]
    success: NotRequired[str]
    error: NotRequired[str]
