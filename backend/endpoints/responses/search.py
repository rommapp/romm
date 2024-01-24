from typing_extensions import TypedDict


class IGDBRom(TypedDict):
    igdb_id: int
    slug: str
    name: str
    summary: str
    url_cover: str
    url_screenshots: list[str]
