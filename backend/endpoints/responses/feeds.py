from typing_extensions import TypedDict

WEBRCADE_SUPPORTED_PLATFORM_SLUGS = [
    "3do",
    "arcade",
    "atari2600",
    "atari5200",
    "atari7800",
    "lynx",
    "wonderswan",
    "wonderswan-color",
    "colecovision",
    "turbografx16--1",
    "turbografx-16-slash-pc-engine-cd",
    "supergrafx",
    "pc-fx",
    "nes",
    "n64",
    "snes",
    "gb",
    "gba",
    "gbc",
    "virtualboy",
    "sg1000",
    "sms",
    "genesis-slash-megadrive",
    "segacd",
    "gamegear",
    "neo-geo-cd",
    "neogeoaes",
    "neogeomvs",
    "neo-geo-pocket",
    "neo-geo-pocket-color",
    "ps",
]

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


class WebrcadeFeedSchema(TypedDict):
    title: str
    longTitle: str
    description: str
    thumbnail: str
    background: str
    categories: list[dict]


class TinfoilFeedSchema(TypedDict):
    files: list[dict]
    directories: list[str]
    success: str
