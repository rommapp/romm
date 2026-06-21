from typing import Any

from pydantic import ConfigDict, model_validator
from sqlalchemy import inspect
from sqlalchemy.exc import InvalidRequestError

from .base import BaseModel, UTCDatetime
from .device import DeviceSyncSchema


class BaseAsset(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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

    created_at: UTCDatetime
    updated_at: UTCDatetime


class ScreenshotSchema(BaseAsset):
    is_gallery: bool = False
    is_public: bool = False


class UserScreenshotSchema(ScreenshotSchema):
    """A gallery screenshot enriched with its owner's username, for the
    community (My / Community) view. Mirrors UserNoteSchema."""

    username: str
    # Author identity for rendering an avatar next to community screenshots.
    user_avatar_path: str = ""
    user_updated_at: UTCDatetime | None = None


class SaveSchema(BaseAsset):
    emulator: str | None
    slot: str | None = None
    content_hash: str | None = None
    is_public: bool = False
    screenshot: ScreenshotSchema | None
    origin_device_id: str | None = None
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


class UserSaveSchema(SaveSchema):
    """A save enriched with its owner's username, for the community (My /
    Community) view. Mirrors UserScreenshotSchema."""

    username: str
    # Author identity for rendering an avatar next to community saves.
    user_avatar_path: str = ""
    user_updated_at: UTCDatetime | None = None


class SlotSummarySchema(BaseModel):
    slot: str | None
    count: int
    latest: SaveSchema


class SaveSummarySchema(BaseModel):
    total_count: int
    slots: list[SlotSummarySchema]


class StateSchema(BaseAsset):
    emulator: str | None
    is_public: bool = False
    screenshot: ScreenshotSchema | None


class UserStateSchema(StateSchema):
    """A state enriched with its owner's username, for the community (My /
    Community) view. Mirrors UserScreenshotSchema."""

    username: str
    # Author identity for rendering an avatar next to community states.
    user_avatar_path: str = ""
    user_updated_at: UTCDatetime | None = None
