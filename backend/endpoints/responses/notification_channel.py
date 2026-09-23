from typing import Annotated, Literal, Self

from pydantic import Field, field_validator

from handler.notification_channels.config import masked_url, read_config
from models.notification import NotificationLevel, NotificationTopic
from models.notification_channel import (
    NOTIFICATION_CHANNEL_NAME_MAX_LENGTH,
    NOTIFICATION_CHANNEL_SECRET_MAX_LENGTH,
    NOTIFICATION_CHANNEL_URL_MAX_LENGTH,
    NotificationChannel,
    NotificationChannelType,
    WebhookFormat,
)
from utils.validation import EMAIL_PATTERN

from .base import BaseModel, UTCDatetime

ChannelName = Annotated[
    str, Field(min_length=1, max_length=NOTIFICATION_CHANNEL_NAME_MAX_LENGTH)
]
WebhookUrl = Annotated[
    str, Field(min_length=1, max_length=NOTIFICATION_CHANNEL_URL_MAX_LENGTH)
]
ChannelSecret = Annotated[str, Field(max_length=NOTIFICATION_CHANNEL_SECRET_MAX_LENGTH)]
EmailAddress = Annotated[str, Field(max_length=320)]


def _check_address(address: str | None) -> str | None:
    if address is not None and not EMAIL_PATTERN.fullmatch(address):
        raise ValueError("Not a valid email address")
    return address


class NotificationChannelSchema(BaseModel):
    id: int
    type: NotificationChannelType
    name: str
    enabled: bool
    min_level: NotificationLevel
    # None forwards every topic.
    topics: list[NotificationTopic] | None
    # A webhook's URL with its token hidden, or an email address.
    target: str
    format: WebhookFormat | None
    has_secret: bool
    confirmed: bool
    last_delivered_at: UTCDatetime | None
    last_error: str | None
    consecutive_failures: int
    created_at: UTCDatetime

    @classmethod
    def from_channel(cls, channel: NotificationChannel) -> Self:
        config = read_config(channel.config)
        is_webhook = channel.type == NotificationChannelType.WEBHOOK
        return cls(
            id=channel.id,
            type=NotificationChannelType(channel.type),
            name=channel.name,
            enabled=channel.enabled,
            min_level=NotificationLevel(channel.min_level),
            topics=(
                [NotificationTopic(topic) for topic in channel.topics]
                if channel.topics is not None
                else None
            ),
            target=(
                masked_url(config["url"])
                if is_webhook and "url" in config
                else config.get("address", "")
            ),
            format=config.get("format") if is_webhook else None,
            has_secret=bool(config.get("secret")),
            confirmed=channel.confirmed_at is not None,
            last_delivered_at=channel.last_delivered_at,
            last_error=channel.last_error,
            consecutive_failures=channel.consecutive_failures,
            created_at=channel.created_at,
        )


class _ChannelFilters(BaseModel):
    min_level: NotificationLevel = NotificationLevel.INFO
    topics: list[NotificationTopic] | None = None


class WebhookChannelCreatePayload(_ChannelFilters):
    type: Literal["webhook"]
    name: ChannelName
    url: WebhookUrl
    format: WebhookFormat = WebhookFormat.JSON
    # The HMAC key of a JSON webhook, or an ntfy access token.
    secret: ChannelSecret | None = None


class EmailChannelCreatePayload(_ChannelFilters):
    type: Literal["email"]
    name: ChannelName
    address: EmailAddress

    check_address = field_validator("address")(_check_address)


NotificationChannelCreatePayload = Annotated[
    WebhookChannelCreatePayload | EmailChannelCreatePayload,
    Field(discriminator="type"),
]


class NotificationChannelUpdatePayload(BaseModel):
    """The fields to change; a null `topics` forwards every topic, an empty `secret` drops it."""

    name: ChannelName | None = None
    enabled: bool | None = None
    min_level: NotificationLevel | None = None
    topics: list[NotificationTopic] | None = None
    url: WebhookUrl | None = None
    format: WebhookFormat | None = None
    secret: ChannelSecret | None = None
    address: EmailAddress | None = None

    check_address = field_validator("address")(_check_address)


class NotificationChannelCodePayload(BaseModel):
    code: str = Field(min_length=1, max_length=16)


class NotificationChannelTestResult(BaseModel):
    ok: bool
    error: str | None
