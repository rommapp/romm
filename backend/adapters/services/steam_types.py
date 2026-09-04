from typing import NotRequired, TypedDict


class SteamPlatforms(TypedDict):
    windows: bool
    mac: bool
    linux: bool


class SteamStoreSearchItem(TypedDict):
    type: str
    name: str
    id: int
    platforms: NotRequired[SteamPlatforms]


class SteamStoreSearchResponse(TypedDict):
    total: int
    items: list[SteamStoreSearchItem]


class SteamGenre(TypedDict):
    id: str
    description: str


class SteamCategory(TypedDict):
    id: int
    description: str


class SteamReleaseDate(TypedDict):
    coming_soon: bool
    date: str


class SteamMetacritic(TypedDict):
    score: int
    url: str


class SteamScreenshot(TypedDict):
    id: int
    path_thumbnail: str
    path_full: str


class SteamAppDetails(TypedDict):
    type: str
    name: str
    steam_appid: int
    # Steam types this as a number for most apps but as a string ("18") for
    # age-gated ones.
    required_age: NotRequired[int | str]
    is_free: NotRequired[bool]
    short_description: NotRequired[str]
    header_image: NotRequired[str]
    capsule_image: NotRequired[str]
    website: NotRequired[str | None]
    developers: NotRequired[list[str]]
    publishers: NotRequired[list[str]]
    platforms: NotRequired[SteamPlatforms]
    metacritic: NotRequired[SteamMetacritic]
    categories: NotRequired[list[SteamCategory]]
    genres: NotRequired[list[SteamGenre]]
    screenshots: NotRequired[list[SteamScreenshot]]
    release_date: NotRequired[SteamReleaseDate]
    controller_support: NotRequired[str]


class SteamAppDetailsEnvelope(TypedDict):
    success: bool
    data: NotRequired[SteamAppDetails]
