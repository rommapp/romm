from typing import Optional

from pydantic import BaseModel
from typing_extensions import TypedDict


class BaseAsset(BaseModel):
    id: int
    file_name: str
    file_name_no_tags: str
    file_extension: str
    file_path: str
    file_size_bytes: int
    full_path: str
    download_path: str

    class Config:
        from_attributes = True


class SaveSchema(BaseAsset):
    rom_id: int
    platform_slug: str
    emulator: Optional[str]


class StateSchema(BaseAsset):
    rom_id: int
    platform_slug: str
    emulator: Optional[str]


class ScreenshotSchema(BaseAsset):
    rom_id: int
    platform_slug: Optional[str]


class UploadedSavesResponse(TypedDict):
    uploaded: int
    saves: list[SaveSchema]


class UploadedStatesResponse(TypedDict):
    uploaded: int
    states: list[StateSchema]
