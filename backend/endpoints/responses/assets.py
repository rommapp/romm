from datetime import datetime
from typing import Any

from pydantic import model_validator
from sqlalchemy import inspect
from sqlalchemy.exc import InvalidRequestError

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

    @model_validator(mode="before")
    @classmethod
    def handle_lazy_relationships(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        try:
            state = inspect(data)
        except Exception:
            return data
        result = {}
        for field_name in cls.model_fields:
            if field_name in state.unloaded:
                continue
            try:
                result[field_name] = getattr(data, field_name)
            except InvalidRequestError:
                continue
        return result


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
