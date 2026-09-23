import json
from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator

from models.notification import (
    MAX_NOTIFICATIONS_PER_USER,
    NOTIFICATION_BODY_MAX_LENGTH,
    NOTIFICATION_DATA_MAX_LENGTH,
    NOTIFICATION_ICON_MAX_LENGTH,
    NOTIFICATION_KIND_MAX_LENGTH,
    NOTIFICATION_LINK_MAX_LENGTH,
    NOTIFICATION_TITLE_MAX_LENGTH,
    NotificationKind,
    NotificationLevel,
)

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
    title: str | None
    body: str | None
    link: str | None
    icon: str | None
    data: dict[str, Any]
    actor: NotificationActorSchema | None
    read_at: UTCDatetime | None
    created_at: UTCDatetime

    @field_validator("data", mode="before")
    @classmethod
    def _data_never_null(cls, value: Any) -> Any:
        return value or {}


class NotificationCreatePayload(BaseModel):
    """A notification sent through the API, shown with its own title and body."""

    title: str = Field(min_length=1, max_length=NOTIFICATION_TITLE_MAX_LENGTH)
    body: str | None = Field(default=None, max_length=NOTIFICATION_BODY_MAX_LENGTH)
    level: NotificationLevel = NotificationLevel.INFO
    # Lets a client tell its own notifications apart, e.g. `argosy.sync_done`.
    kind: str = Field(
        default=NotificationKind.CUSTOM,
        max_length=NOTIFICATION_KIND_MAX_LENGTH,
        pattern=r"^[a-z0-9][a-z0-9_.:-]*$",
    )
    link: str | None = Field(
        default=None,
        max_length=NOTIFICATION_LINK_MAX_LENGTH,
        description="A path inside RomM, such as `/rom/12`.",
    )
    icon: str | None = Field(
        default=None,
        max_length=NOTIFICATION_ICON_MAX_LENGTH,
        pattern=r"^mdi-[a-z0-9-]+$",
        description="A Material Design Icons name, such as `mdi-sync`.",
    )
    data: dict[str, Any] = Field(default_factory=dict)
    recipients: list[int] | Literal["admins", "all"] | None = Field(
        default=None,
        description="User ids, `admins` or `all`; only an admin may notify "
        "anyone but themselves. Null notifies the caller.",
    )

    @field_validator("kind")
    @classmethod
    def _kind_not_reserved(cls, value: str) -> str:
        # Stops a client passing itself off as one of RomM's own events.
        if value != NotificationKind.CUSTOM and value in NotificationKind:
            raise ValueError(f"'{value}' is reserved for RomM's own notifications")
        return value

    @field_validator("title", "body", "link")
    @classmethod
    def _no_nul(cls, value: str | None) -> str | None:
        # PostgreSQL refuses NUL in text columns.
        if value is not None and "\x00" in value:
            raise ValueError("must not contain NUL characters")
        return value

    @field_validator("recipients")
    @classmethod
    def _names_someone(
        cls, value: list[int] | Literal["admins", "all"] | None
    ) -> list[int] | Literal["admins", "all"] | None:
        if value == []:
            raise ValueError("must name at least one user")
        return value

    @field_validator("data")
    @classmethod
    def _data_fits(cls, value: dict[str, Any]) -> dict[str, Any]:
        # `allow_nan=False` rejects NaN and Infinity, which no database stores as JSON.
        if len(json.dumps(value, allow_nan=False)) > NOTIFICATION_DATA_MAX_LENGTH:
            raise ValueError(
                f"data must serialize to at most {NOTIFICATION_DATA_MAX_LENGTH} characters"
            )
        return value

    @field_validator("link")
    @classmethod
    def _link_stays_in_app(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if (
            not value.startswith("/")
            or value.startswith("//")
            or "\\" in value
            or any(char.isspace() for char in value)
        ):
            raise ValueError("link must be a path inside RomM, such as /rom/12")
        return value


class NotificationIdsPayload(BaseModel):
    """Targets some of the caller's notifications, or all of them when `ids` is null."""

    ids: list[int] | None = Field(default=None, max_length=MAX_NOTIFICATIONS_PER_USER)
