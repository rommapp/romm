import uuid
from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator
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
    """The file name, extension included."""
    file_name_no_tags: str
    """The file name without its extension or any tags in parentheses or brackets."""
    file_name_no_ext: str
    file_extension: str
    file_path: str
    """The folder holding the file."""
    file_size_bytes: int
    full_path: str
    download_path: str

    missing_from_fs: bool

    created_at: UTCDatetime
    updated_at: UTCDatetime


class AssetAnnotations(BaseModel):
    """The owner-only annotations saves and states share."""

    is_favorite: bool = False
    labels: list[str] = []
    """The owner's free-text labels."""

    @field_validator("labels", mode="before")
    @classmethod
    def _labels_never_null(cls, value: Any) -> Any:
        # The column is nullable, so rows predating the migration read NULL.
        return value or []


# A shared save or state shows its author's name, never their annotations:
# a label names a run for its owner and is not part of what sharing offers.
# Derived from the model so a field added there is masked without a second edit.
HIDDEN_ASSET_ANNOTATIONS: dict[str, Any] = AssetAnnotations().model_dump()


class ScreenshotSchema(BaseAsset):
    is_gallery: bool = False
    """True for a screenshot shown in the gallery, and false for a thumbnail captured with a save or state."""
    is_public: bool = False


class UserScreenshotSchema(ScreenshotSchema):
    """A gallery screenshot enriched with its owner's username, for the
    community (My / Community) view. Mirrors UserNoteSchema."""

    username: str
    # Author identity for rendering an avatar next to community screenshots.
    user_avatar_path: str = ""
    user_updated_at: UTCDatetime | None = None


class ManagedAsset(BaseModel):
    channel_id: uuid.UUID | None = None
    """The ID of the sync channel this was pushed to. Null for a backup that the user manages themselves."""
    content_hash: str | None = None
    """MD5 of the file's bytes, or for a zip, of its sorted `name:md5` entry lines. Null for a file never hashed."""


class SaveSchema(BaseAsset, AssetAnnotations, ManagedAsset):
    emulator: str | None
    slot: str | None = None
    is_public: bool = False
    screenshot: ScreenshotSchema | None
    origin_device_id: str | None = None
    device_syncs: list[DeviceSyncSchema] = []
    """The sync state of each device that has synced the save, starting with the device given in `device_id`. Empty when the request has no `device_id`."""

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


class SaveLayoutOptionSchema(BaseModel):
    """A core option a layout's files read. `values` is empty for a free-form
    value; a `default` of "" means the files need the option set."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    values: list[str]
    """The allowed values. Empty for a free-form value."""
    default: str
    """The default value. Empty when the option has no default and must be set."""


class SaveLayoutSchema(BaseModel):
    """One of sigil's save layouts: `id` is what the content route takes as `core`."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    """The ID of the layout, which the content route takes as `core`."""
    platform: str = Field(description='Sigil\'s platform slug, "" for any platform')
    options: list[SaveLayoutOptionSchema]
    """The core options that the layout's files depend on."""
    region_option: str = Field(
        description='The option that picks a shared file by the disc\'s region, or ""'
    )
    profiles: bool = Field(description="An account save needs a user profile")
    needs_existing: bool = Field(
        description="Restore names a new file only once one of the game's files is there"
    )


class StateSchema(BaseAsset, AssetAnnotations, ManagedAsset):
    emulator: str | None
    core: str | None = None
    """The libretro core that wrote the state."""
    is_public: bool = False
    screenshot: ScreenshotSchema | None
    origin_device_id: str | None = None


class UserStateSchema(StateSchema):
    """A state enriched with its owner's username, for the community (My /
    Community) view. Mirrors UserScreenshotSchema."""

    username: str
    # Author identity for rendering an avatar next to community states.
    user_avatar_path: str = ""
    user_updated_at: UTCDatetime | None = None
