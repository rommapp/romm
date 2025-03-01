from typing import NotRequired, TypedDict

WEBRCADE_SUPPORTED_PLATFORM_SLUGS = frozenset(
    (
        "3do",
        "arcade",
        "atari2600",
        "atari5200",
        "atari7800",
        "colecovision",
        "gamegear",
        "gb",
        "gba",
        "gbc",
        "megadrive",
        "lynx",
        "n64",
        "neogeocd",
        "ngp",
        "ngpc",
        "neogeoaes",
        "neogeomvs",
        "nes",
        "pcfx",
        "psx",
        "segacd",
        "sg1000",
        "sms",
        "snes",
        "supergrafx",
        "pcenginecd",
        "pcengine",
        "virtualboy",
        "wswan",
        "wswanc",
    )
)

WEBRCADE_SLUG_TO_TYPE_MAP = {
    "atari2600": "2600",
    "atari5200": "5200",
    "atari7800": "7800",
    "lynx": "lnx",
    "pcengine": "pce",
    "pcenginecd": "pce",
    "supergrafx": "sgx",
    "pcfx": "pcfx",
    "virtualboy": "vb",
    "megadrive": "genesis",
    "gamegear": "gg",
    "neogeoaes": "neogeo",
    "neogeomvs": "neogeo",
    "neogeocd": "neogeocd",
    "ngp": "ngp",
    "ngpc": "ngc",
    "psx": "psx",
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
