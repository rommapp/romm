from typing import Any

from pydantic import ConfigDict, field_validator

from models.notification import NotificationKind, NotificationLevel

from .base import BaseModel, UTCDatetime


class NotificationActorSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    avatar_path: str
    updated_at: UTCDatetime


class NotificationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # A row written under a kind a later version dropped must still list.
    kind: NotificationKind | str
    level: NotificationLevel
    data: dict[str, Any]
    actor: NotificationActorSchema | None
    read_at: UTCDatetime | None
    created_at: UTCDatetime

    @field_validator("data", mode="before")
    @classmethod
    def _data_never_null(cls, value: Any) -> Any:
        return value or {}


class NotificationIdsPayload(BaseModel):
    """Targets some of the caller's notifications, or all of them when `ids` is null."""

    ids: list[int] | None = None
