from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from typing_extensions import TypedDict


class BaseAsset(BaseModel):
    id: int
    file_name: str
    file_name_no_tags: str
    file_name_no_ext: str
    file_extension: str
    file_path: str
    file_size_bytes: int
    full_path: str
    download_path: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScreenshotSchema(BaseAsset):
    rom_id: int


class UploadedScreenshotsResponse(TypedDict):
    uploaded: int
    screenshots: list[ScreenshotSchema]
    url_screenshots: list[str]
    merged_screenshots: list[str]


class SaveSchema(BaseAsset):
    rom_id: int
    emulator: Optional[str]
    screenshot: Optional[ScreenshotSchema]


class UploadedSavesResponse(TypedDict):
    uploaded: int
    saves: list[SaveSchema]


class StateSchema(BaseAsset):
    rom_id: int
    emulator: Optional[str]
    screenshot: Optional[ScreenshotSchema]


class UploadedStatesResponse(TypedDict):
    uploaded: int
    states: list[StateSchema]
