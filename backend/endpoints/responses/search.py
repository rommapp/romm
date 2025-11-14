from handler.metadata.sgdb_handler import SGDBResource

from .base import BaseModel


class SearchRomSchema(BaseModel):
    id: int | None = None
    igdb_id: int | None = None
    moby_id: int | None = None
    ss_id: int | None = None
    sgdb_id: int | None = None
    flashpoint_id: str | None = None
    launchbox_id: int | None = None
    platform_id: int
    name: str
    slug: str = ""
    summary: str = ""
    igdb_url_cover: str = ""
    moby_url_cover: str = ""
    ss_url_cover: str = ""
    sgdb_url_cover: str = ""
    flashpoint_url_cover: str = ""
    launchbox_url_cover: str = ""
    is_unidentified: bool
    is_identified: bool


class SearchCoverSchema(BaseModel):
    name: str
    resources: list[SGDBResource]
