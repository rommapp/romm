from typing import Literal, TypedDict

MobyOutputFormat = Literal["id", "brief", "normal"]


class MobyGameAlternateTitle(TypedDict):
    description: str
    title: str


class MobyGenre(TypedDict):
    genre_category: str
    genre_category_id: int
    genre_id: int
    genre_name: str


class MobyPlatform(TypedDict):
    first_release_date: str
    platform_id: int
    platform_name: str


class MobyGameCover(TypedDict):
    height: int
    image: str
    platforms: list[str]
    thumbnail_image: str
    width: int


class MobyGameScreenshot(TypedDict):
    caption: str
    height: int
    image: str
    thumbnail_image: str
    width: int


# https://www.mobygames.com/info/api/#games
class MobyGameBrief(TypedDict):
    game_id: int
    moby_url: str
    title: str


# https://www.mobygames.com/info/api/#games
class MobyGame(TypedDict):
    alternate_titles: list[MobyGameAlternateTitle]
    description: str
    game_id: int
    genres: list[MobyGenre]
    moby_score: float
    moby_url: str
    num_votes: int
    official_url: str | None
    platforms: list[MobyPlatform]
    sample_cover: MobyGameCover
    sample_screenshots: list[MobyGameScreenshot]
    title: str
