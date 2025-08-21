import enum
from collections.abc import Mapping
from typing import TypedDict


@enum.unique
class SGDBStyle(enum.StrEnum):
    ALTERNATE = "alternate"
    BLURRED = "blurred"
    WHITE_LOGO = "white_logo"
    MATERIAL = "material"
    NO_LOGO = "no_logo"


@enum.unique
class SGDBDimension(enum.StrEnum):
    STEAM_HORIZONTAL = "460x215"
    STEAM_HORIZONTAL_2X = "920x430"
    STEAM_VERTICAL = "600x900"
    GOG_GALAXY_TILE = "342x482"
    GOG_GALAXY_COVER = "660x930"
    SQUARE_512 = "512x512"
    SQUARE_1024 = "1024x1024"


@enum.unique
class SGDBMime(enum.StrEnum):
    PNG = "image/png"
    JPEG = "image/jpeg"
    WEBP = "image/webp"


@enum.unique
class SGDBType(enum.StrEnum):
    STATIC = "static"
    ANIMATED = "animated"


@enum.unique
class SGDBTag(enum.StrEnum):
    HUMOR = "humor"
    NSFW = "nsfw"
    EPILEPSY = "epilepsy"


class PaginatedResponse[T: Mapping](TypedDict):
    page: int
    total: int
    limit: int
    data: list[T]


class SGDBGridAuthor(TypedDict):
    name: str
    steam64: str
    avatar: str


class SGDBGrid(TypedDict):
    id: int
    score: int
    style: SGDBStyle
    url: str
    thumb: str
    tags: list[str]
    author: SGDBGridAuthor


class SGDBGame(TypedDict):
    id: int
    name: str
    types: list[str]
    verified: bool


SGDBGridList = PaginatedResponse[SGDBGrid]
