from .base import BaseModel


class SearchRomSchema(BaseModel):
    id: int | None = None
    igdb_id: int | None = None
    moby_id: int | None = None
    ss_id: int | None = None
    sgdb_id: int | None = None
    platform_id: int
    name: str
    slug: str = ""
    summary: str = ""
    igdb_url_cover: str = ""
    moby_url_cover: str = ""
    ss_url_cover: str = ""
    sgdb_url_cover: str = ""


class SearchCoverSchema(BaseModel):
    name: str
    resources: list
