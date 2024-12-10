from pydantic import BaseModel


class SearchRomSchema(BaseModel):
    igdb_id: int | None = None
    moby_id: int | None = None
    slug: str
    name: str
    summary: str
    igdb_url_cover: str = ""
    moby_url_cover: str = ""
    platform_id: int


class SearchCoverSchema(BaseModel):
    name: str
    resources: list
