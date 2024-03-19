from pydantic import BaseModel

class SearchRomSchema(BaseModel):
    igdb_id: int | None = None
    moby_id: int | None = None
    slug: str
    name: str
    summary: str
    url_cover: str
    url_screenshots: list[str]
