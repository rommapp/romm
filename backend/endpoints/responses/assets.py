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
    """The internal ID."""
    rom_id: int
    """The internal ID of the rom."""
    user_id: int
    """The ID of the user who owns it."""
    file_name: str
    """The file name, extension included."""
    file_name_no_tags: str
    """The file name without its extension or any tags in parentheses or brackets."""
    file_name_no_ext: str
    """The file name without its extension."""
    file_extension: str
    """The file extension."""
    file_path: str
    """The folder holding the file."""
    file_size_bytes: int
    """The size of the file, in bytes."""
    full_path: str
    """The path to the file on disk."""
    download_path: str
    """The path to download the file from."""

    missing_from_fs: bool
    """True when the file is no longer on disk."""

    created_at: UTCDatetime
    """When the record was created."""
    updated_at: UTCDatetime
    """When the record last changed."""


class AssetAnnotations(BaseModel):
    """The owner-only annotations saves and states share."""

    is_favorite: bool = False
    """Whether the owner marked it as a favorite."""
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
    """True for a screenshot shown in the gallery. Thumbnails captured with saves and states are not."""
    is_public: bool = False
    """Whether other users can see the screenshot."""


class UserScreenshotSchema(ScreenshotSchema):
    """A gallery screenshot enriched with its owner's username, for the
    community (My / Community) view. Mirrors UserNoteSchema."""

    username: str
    """The username of the owner."""
    # Author identity for rendering an avatar next to community screenshots.
    user_avatar_path: str = ""
    """The path to the owner's avatar."""
    user_updated_at: UTCDatetime | None = None
    """When the owner's record last changed."""


class ManagedAsset(BaseModel):
    channel_id: uuid.UUID | None = None
    """The ID of the sync channel the row was pushed into. Null means a backup the user manages."""


class SaveSchema(BaseAsset, AssetAnnotations, ManagedAsset):
    emulator: str | None
    """The emulator that wrote the save."""
    slot: str | None = None
    """The slot the save belongs to. Null for a save without a slot."""
    content_hash: str | None = None
    """The hash of the save file's content."""
    is_public: bool = False
    """Whether other users can see the save."""
    screenshot: ScreenshotSchema | None
    """The screenshot stored with the save."""
    origin_device_id: str | None = None
    """The ID of the device the save came from."""
    device_syncs: list[DeviceSyncSchema] = []
    """The sync state of every device that synced the save, the named device first. Empty when the request names no device."""

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
    """The username of the owner."""
    # Author identity for rendering an avatar next to community saves.
    user_avatar_path: str = ""
    """The path to the owner's avatar."""
    user_updated_at: UTCDatetime | None = None
    """When the owner's record last changed."""


class SlotSummarySchema(BaseModel):
    slot: str | None
    """The slot name. Null for saves without a slot."""
    count: int
    """The number of saves in the slot."""
    latest: SaveSchema
    """The newest save in the slot."""


class SaveSummarySchema(BaseModel):
    total_count: int
    """The number of saves for the rom."""
    slots: list[SlotSummarySchema]
    """A summary of each slot."""


class SaveLayoutOptionSchema(BaseModel):
    """A core option a layout's files read. `values` is empty for a free-form
    value; a `default` of "" means the files need the option set."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    """The key of the option."""
    values: list[str]
    """The allowed values. Empty for a free-form value."""
    default: str
    """The default value. Empty means the files need the option set."""


class SaveLayoutSchema(BaseModel):
    """One of sigil's save layouts: `id` is what the content route takes as `core`."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    """The ID of the layout. The content route takes it as `core`."""
    platform: str = Field(description='Sigil\'s platform slug, "" for any platform')
    options: list[SaveLayoutOptionSchema]
    """The core options the layout's files read."""
    region_option: str = Field(
        description='The option that picks a shared file by the disc\'s region, or ""'
    )
    profiles: bool = Field(description="An account save needs a user profile")
    needs_existing: bool = Field(
        description="Restore names a new file only once one of the game's files is there"
    )


class StateSchema(BaseAsset, AssetAnnotations, ManagedAsset):
    emulator: str | None
    """The emulator that wrote the state."""
    core: str | None = None
    """The libretro core that wrote the state."""
    is_public: bool = False
    """Whether other users can see the state."""
    screenshot: ScreenshotSchema | None
    """The screenshot stored with the state."""
    origin_device_id: str | None = None
    """The ID of the device the state came from."""


class UserStateSchema(StateSchema):
    """A state enriched with its owner's username, for the community (My /
    Community) view. Mirrors UserScreenshotSchema."""

    username: str
    """The username of the owner."""
    # Author identity for rendering an avatar next to community states.
    user_avatar_path: str = ""
    """The path to the owner's avatar."""
    user_updated_at: UTCDatetime | None = None
    """When the owner's record last changed."""
