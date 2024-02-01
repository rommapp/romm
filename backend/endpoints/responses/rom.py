from typing import Optional

from endpoints.responses.assets import SaveSchema, ScreenshotSchema, StateSchema
from fastapi.responses import StreamingResponse
from handler import socket_handler
from pydantic import BaseModel
from typing_extensions import TypedDict


class RomSchema(BaseModel):
    id: int
    igdb_id: Optional[int]
    sgdb_id: Optional[int]

    platform_id: int
    platform_slug: str
    platform_name: str

    file_name: str
    file_name_no_tags: str
    file_name_no_ext: str
    file_extension: str
    file_path: str
    file_size_bytes: int

    name: Optional[str]
    slug: Optional[str]
    summary: Optional[str]
    total_rating: Optional[str]
    genres: list[str]

    sort_comparator: str

    path_cover_s: Optional[str]
    path_cover_l: Optional[str]
    has_cover: bool
    url_cover: Optional[str]

    revision: Optional[str]
    regions: list[str]
    languages: list[str]
    tags: list[str]

    multi: bool
    files: list[str]
    saves: list[SaveSchema]
    states: list[StateSchema]
    screenshots: list[ScreenshotSchema]
    url_screenshots: list[str]
    merged_screenshots: list[str]
    full_path: str
    download_path: str

    class Config:
        from_attributes = True


class EnhancedRomSchema(RomSchema):
    sibling_roms: list["RomSchema"]


class AddRomsResponse(TypedDict):
    uploaded_roms: list[str]
    skipped_roms: list[str]


class CustomStreamingResponse(StreamingResponse):
    def __init__(self, *args, **kwargs) -> None:
        self.emit_body = kwargs.pop("emit_body", None)
        super().__init__(*args, **kwargs)

    async def stream_response(self, *args, **kwargs) -> None:
        await super().stream_response(*args, **kwargs)
        await socket_handler.socket_server.emit("download:complete", self.emit_body)
