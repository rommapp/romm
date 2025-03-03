from .base import BaseModel


class SearchRomSchema(BaseModel):
    id: int
    igdb_id: int | None = None
    moby_id: int | None = None
    ss_id: int | None = None
    slug: str
    name: str
    summary: str
    igdb_url_cover: str = ""
    moby_url_cover: str = ""
    ss_url_cover: str = ""
    platform_id: int


class SearchCoverSchema(BaseModel):
    name: str
    resources: list
