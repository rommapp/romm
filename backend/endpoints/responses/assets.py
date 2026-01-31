from datetime import datetime

from .base import BaseModel
from .device import DeviceSyncSchema


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

    missing_from_fs: bool

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScreenshotSchema(BaseAsset):
    pass


class SaveSchema(BaseAsset):
    emulator: str | None
    slot: str | None = None
    content_hash: str | None = None
    screenshot: ScreenshotSchema | None
    device_syncs: list[DeviceSyncSchema] = []


class SlotSummarySchema(BaseModel):
    slot: str | None
    count: int
    latest: SaveSchema


class SaveSummarySchema(BaseModel):
    total_count: int
    slots: list[SlotSummarySchema]


class StateSchema(BaseAsset):
    emulator: str | None
    screenshot: ScreenshotSchema | None
