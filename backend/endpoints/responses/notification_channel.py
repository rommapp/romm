from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, field_validator

from handler.notification_channels import apprise_channel
from handler.notification_channels.apprise_channel import (
    AppriseField,
    AppriseService,
    FieldType,
)
from handler.notification_channels.config import masked_url, read_config
from models.notification import NotificationTopic
from models.notification_channel import (
    NOTIFICATION_CHANNEL_ADDRESS_MAX_LENGTH,
    NOTIFICATION_CHANNEL_CODE_MAX_LENGTH,
    NOTIFICATION_CHANNEL_MAX_FIELDS,
    NOTIFICATION_CHANNEL_NAME_MAX_LENGTH,
    NOTIFICATION_CHANNEL_SECRET_MAX_LENGTH,
    NOTIFICATION_CHANNEL_SERVICE_MAX_LENGTH,
    NOTIFICATION_CHANNEL_URL_MAX_LENGTH,
    NotificationChannel,
    NotificationChannelMinLevel,
    NotificationChannelType,
)
from utils.validation import EMAIL_PATTERN

from .base import BaseModel, UTCDatetime

ChannelName = Annotated[
    str, Field(min_length=1, max_length=NOTIFICATION_CHANNEL_NAME_MAX_LENGTH)
]
ChannelUrl = Annotated[
    str, Field(min_length=1, max_length=NOTIFICATION_CHANNEL_URL_MAX_LENGTH)
]
ChannelSecret = Annotated[str, Field(max_length=NOTIFICATION_CHANNEL_SECRET_MAX_LENGTH)]
EmailAddress = Annotated[str, Field(max_length=NOTIFICATION_CHANNEL_ADDRESS_MAX_LENGTH)]
AppriseServiceId = Annotated[
    str, Field(min_length=1, max_length=NOTIFICATION_CHANNEL_SERVICE_MAX_LENGTH)
]
_FieldText = Annotated[str, Field(max_length=NOTIFICATION_CHANNEL_URL_MAX_LENGTH)]
AppriseFieldValue = StrictBool | int | float | _FieldText | list[_FieldText]
AppriseFields = Annotated[
    dict[str, AppriseFieldValue], Field(max_length=NOTIFICATION_CHANNEL_MAX_FIELDS)
]


def _check_address(address: str | None) -> str | None:
    if address is not None and not EMAIL_PATTERN.fullmatch(address):
        raise ValueError("Not a valid email address")
    return address


class NotificationChannelSchema(BaseModel):
    id: int
    type: NotificationChannelType
    name: str
    enabled: bool
    min_level: NotificationChannelMinLevel
    # None forwards every topic.
    topics: list[NotificationTopic] | None
    # The URL with its secrets hidden, or an email address.
    target: str
    # An Apprise channel's service, its name, and the fields that aren't secrets.
    service: str | None
    service_name: str | None
    fields: dict[str, AppriseFieldValue] | None
    has_secret: bool
    confirmed: bool
    last_delivered_at: UTCDatetime | None
    last_error: str | None
    consecutive_failures: int
    created_at: UTCDatetime

    @classmethod
    def from_channel(cls, channel: NotificationChannel) -> Self:
        config = read_config(channel.config)
        service = config.get("service")
        stored_fields = config.get("fields", {})
        service_name, fields = None, None
        match channel.type:
            case NotificationChannelType.APPRISE if service:
                service_name, target = apprise_channel.describe(service, stored_fields)
                fields = apprise_channel.public_fields(service, stored_fields)
            case NotificationChannelType.WEBHOOK if config.get("url"):
                target = masked_url(config["url"])
            case _:
                target = config.get("address", "")
        return cls(
            id=channel.id,
            type=NotificationChannelType(channel.type),
            name=channel.name,
            enabled=channel.enabled,
            min_level=NotificationChannelMinLevel(channel.min_level),
            topics=(
                [NotificationTopic(topic) for topic in channel.topics]
                if channel.topics is not None
                else None
            ),
            target=target,
            service=service,
            service_name=service_name,
            fields=fields,
            has_secret=bool(config.get("secret")),
            confirmed=channel.confirmed_at is not None,
            last_delivered_at=channel.last_delivered_at,
            last_error=channel.last_error,
            consecutive_failures=channel.consecutive_failures,
            created_at=channel.created_at,
        )


class _ChannelFilters(BaseModel):
    min_level: NotificationChannelMinLevel = NotificationChannelMinLevel.INFO
    topics: list[NotificationTopic] | None = None


class AppriseChannelCreatePayload(_ChannelFilters):
    type: Literal["apprise"]
    name: ChannelName
    service: AppriseServiceId
    fields: AppriseFields


class WebhookChannelCreatePayload(_ChannelFilters):
    type: Literal["webhook"]
    name: ChannelName
    url: ChannelUrl
    # The key the payload is signed with.
    secret: ChannelSecret | None = None


class EmailChannelCreatePayload(_ChannelFilters):
    type: Literal["email"]
    name: ChannelName
    address: EmailAddress

    check_address = field_validator("address")(_check_address)


NotificationChannelCreatePayload = Annotated[
    AppriseChannelCreatePayload
    | WebhookChannelCreatePayload
    | EmailChannelCreatePayload,
    Field(discriminator="type"),
]


class NotificationChannelUpdatePayload(BaseModel):
    """The fields to change; a null `topics` forwards every topic, an empty `secret` drops it."""

    name: ChannelName | None = None
    enabled: bool | None = None
    min_level: NotificationChannelMinLevel | None = None
    topics: list[NotificationTopic] | None = None
    url: ChannelUrl | None = None
    secret: ChannelSecret | None = None
    address: EmailAddress | None = None
    # An Apprise channel's fields; a secret left out keeps its current value.
    fields: AppriseFields | None = None

    check_address = field_validator("address")(_check_address)


class NotificationChannelCodePayload(BaseModel):
    code: str = Field(min_length=1, max_length=NOTIFICATION_CHANNEL_CODE_MAX_LENGTH)


class AppriseFieldSchema(BaseModel):
    key: str
    label: str
    type: FieldType
    required: bool
    private: bool
    # Sent as an option rather than as part of the address.
    advanced: bool
    default: AppriseFieldValue | None
    # A choice's values, as text: that is how they sit in the URL.
    values: list[str] | None
    min: float | None
    max: float | None

    @classmethod
    def from_field(cls, field: AppriseField) -> Self:
        return cls(
            key=field.key,
            label=field.label,
            type=field.type,
            required=field.required,
            private=field.private,
            advanced=field.advanced,
            default=field.default,
            values=[str(value) for value in field.values] if field.values else None,
            min=field.min,
            max=field.max,
        )


class AppriseServiceSchema(BaseModel):
    id: str
    name: str
    setup_url: str | None
    fields: list[AppriseFieldSchema]

    @classmethod
    def from_service(cls, service: AppriseService) -> Self:
        return cls(
            id=service.id,
            name=service.name,
            setup_url=service.setup_url,
            fields=[AppriseFieldSchema.from_field(field) for field in service.fields],
        )


class NotificationChannelTestResult(BaseModel):
    ok: bool
    error: str | None
