from typing import Literal

from pydantic import ConfigDict, Field

from models.shortcut import LaunchMode, ShortcutStatus

from .base import BaseModel, UTCDatetime


class ShortcutSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    device_id: str
    rom_id: int
    status: ShortcutStatus
    launch_mode: LaunchMode | None
    steam_app_id: int | None
    error: str | None
    created_at: UTCDatetime
    updated_at: UTCDatetime


class ShortcutCreatePayload(BaseModel):
    device_id: str
    rom_id: int
    launch_mode: LaunchMode | None = None


class ShortcutAckStatus(BaseModel):
    """Outcome a launcher client reports for one queued shortcut."""

    status: Literal["staged", "added", "failed", "removed"] = Field(
        description="Lifecycle outcome; removed deletes the row."
    )
    steam_app_id: int | None = Field(default=None, ge=0, le=0xFFFFFFFF)
    error: str | None = Field(default=None, max_length=2000)


class SteamArtworkSchema(BaseModel):
    """The Steam library art a launcher client writes beside RomM's cover."""

    url_hero: str | None = Field(
        default=None, description="Wide banner for the game's Steam page."
    )
    url_logo: str | None = Field(
        default=None, description="Transparent title treatment drawn over the hero."
    )
