from datetime import datetime
from typing import TypedDict

from pydantic import BaseModel


class BaseAsset(BaseModel):
    id: int
    rom_id: int
    user_id: int
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
    pass


class UploadedScreenshotsResponse(TypedDict):
    uploaded: int
    screenshots: list[ScreenshotSchema]
    merged_screenshots: list[str]


class SaveSchema(BaseAsset):
    emulator: str | None
    screenshot: ScreenshotSchema | None


class UploadedSavesResponse(TypedDict):
    uploaded: int
    saves: list[SaveSchema]


class StateSchema(BaseAsset):
    emulator: str | None
    screenshot: ScreenshotSchema | None


class UploadedStatesResponse(TypedDict):
    uploaded: int
    states: list[StateSchema]
