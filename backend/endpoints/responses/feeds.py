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
        "genesis-slash-megadrive",
        "lynx",
        "n64",
        "neo-geo-cd",
        "neo-geo-pocket",
        "neo-geo-pocket-color",
        "neogeoaes",
        "neogeomvs",
        "nes",
        "pc-fx",
        "ps",
        "segacd",
        "sg1000",
        "sms",
        "snes",
        "supergrafx",
        "turbografx-16-slash-pc-engine-cd",
        "turbografx16--1",
        "virtualboy",
        "wonderswan",
        "wonderswan-color",
    )
)

WEBRCADE_SLUG_TO_TYPE_MAP = {
    "atari2600": "2600",
    "atari5200": "5200",
    "atari7800": "7800",
    "lynx": "lnx",
    "turbografx16--1": "pce",
    "turbografx-16-slash-pc-engine-cd": "pce",
    "supergrafx": "sgx",
    "pc-fx": "pcfx",
    "virtualboy": "vb",
    "genesis-slash-megadrive": "genesis",
    "gamegear": "gg",
    "neogeoaes": "neogeo",
    "neogeomvs": "neogeo",
    "neo-geo-cd": "neogeocd",
    "neo-geo-pocket": "ngp",
    "neo-geo-pocket-color": "ngc",
    "ps": "psx",
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


class TinfoilFeedSchema(TypedDict):
    files: list[TinfoilFeedFileSchema]
    directories: list[str]
    success: NotRequired[str]
    error: NotRequired[str]
