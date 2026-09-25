from collections.abc import Awaitable
from functools import cache
from typing import TypeVar

from fastapi import HTTPException, Request, status

from decorators.auth import protected_route
from endpoints.responses.notification_channel import (
    AppriseChannelCreatePayload,
    AppriseServiceSchema,
    EmailChannelCreatePayload,
    NotificationChannelCodePayload,
    NotificationChannelCreatePayload,
    NotificationChannelSchema,
    NotificationChannelTestResult,
    NotificationChannelUpdatePayload,
)
from handler.auth.constants import Scope
from handler.database import db_notification_channel_handler
from handler.email_handler import EmailError
from handler.notification_channels import apprise_channel, channels
from handler.notification_channels.channels import ChannelError
from handler.notification_channels.confirmation import CodeCooldownError
from models.notification_channel import NotificationChannel, NotificationChannelType
from models.user import User
from utils.router import APIRouter

router = APIRouter(
    prefix="/notification-channels",
    tags=["notification-channels"],
)

_T = TypeVar("_T")


def _get_or_404(channel_id: int, user: User) -> NotificationChannel:
    channel = db_notification_channel_handler.get_channel(channel_id, user.id)
    if channel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification channel not found",
        )
    return channel


async def _as_http(action: Awaitable[_T]) -> _T:
    """Await a channel action, turning its errors into the matching HTTP status."""
    try:
        return await action
    except ChannelError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except CodeCooldownError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        ) from exc
    except EmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc


@protected_route(router.get, "", [Scope.ME_READ])
def get_notification_channels(request: Request) -> list[NotificationChannelSchema]:
    """The caller's notification channels."""
    return [
        NotificationChannelSchema.from_channel(channel)
        for channel in db_notification_channel_handler.get_channels(request.user.id)
    ]


@protected_route(router.get, "/apprise-services", [Scope.ME_READ])
def get_apprise_services(request: Request) -> list[AppriseServiceSchema]:
    """Every service an admin's Apprise channel can go out on, with its fields."""
    try:
        channels.require_apprise(request.user)
    except ChannelError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    return _apprise_catalog()


@cache
def _apprise_catalog() -> list[AppriseServiceSchema]:
    return [AppriseServiceSchema.from_service(s) for s in apprise_channel.services()]


@protected_route(router.post, "", [Scope.ME_WRITE], status_code=status.HTTP_201_CREATED)
async def create_notification_channel(
    request: Request, payload: NotificationChannelCreatePayload
) -> NotificationChannelSchema:
    """Add a channel; an email address gets a code to confirm it with first."""
    match payload:
        case EmailChannelCreatePayload():
            created = channels.create_channel(
                request.user,
                NotificationChannelType.EMAIL,
                payload.name,
                payload.min_level,
                payload.topics,
                address=payload.address,
            )
        case AppriseChannelCreatePayload():
            created = channels.create_channel(
                request.user,
                NotificationChannelType.APPRISE,
                payload.name,
                payload.min_level,
                payload.topics,
                service=payload.service,
                fields=payload.fields,
            )
        case _:
            created = channels.create_channel(
                request.user,
                NotificationChannelType.WEBHOOK,
                payload.name,
                payload.min_level,
                payload.topics,
                url=payload.url,
                secret=payload.secret,
            )
    return NotificationChannelSchema.from_channel(await _as_http(created))


@protected_route(router.patch, "/{channel_id}", [Scope.ME_WRITE])
async def update_notification_channel(
    request: Request, channel_id: int, payload: NotificationChannelUpdatePayload
) -> NotificationChannelSchema:
    """Change a channel; a new email address has to be confirmed again."""
    changes = {
        field: value
        for field, value in payload.model_dump(
            include={"name", "enabled", "min_level"}
        ).items()
        if value is not None
    }
    if "topics" in payload.model_fields_set:
        changes["topics"] = payload.topics

    updated = await _as_http(
        channels.update_channel(
            _get_or_404(channel_id, request.user),
            request.user,
            changes,
            url=payload.url,
            secret=payload.secret,
            secret_given="secret" in payload.model_fields_set,
            address=payload.address,
            fields=payload.fields,
        )
    )
    return NotificationChannelSchema.from_channel(updated)


@protected_route(router.delete, "/{channel_id}", [Scope.ME_WRITE])
def delete_notification_channel(request: Request, channel_id: int) -> None:
    if not db_notification_channel_handler.delete_channel(channel_id, request.user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification channel not found",
        )


@protected_route(router.post, "/{channel_id}/test", [Scope.ME_WRITE])
async def test_notification_channel(
    request: Request, channel_id: int
) -> NotificationChannelTestResult:
    """Send a sample notification out on the channel right away."""
    error = await _as_http(
        channels.send_sample(_get_or_404(channel_id, request.user), request.user)
    )
    return NotificationChannelTestResult(ok=error is None, error=error)


@protected_route(router.post, "/{channel_id}/confirm", [Scope.ME_WRITE])
async def confirm_notification_channel(
    request: Request, channel_id: int, payload: NotificationChannelCodePayload
) -> NotificationChannelSchema:
    """Confirm an email address with the code sent to it."""
    confirmed = await _as_http(
        channels.confirm_channel(
            _get_or_404(channel_id, request.user), request.user, payload.code
        )
    )
    return NotificationChannelSchema.from_channel(confirmed)


@protected_route(
    router.post,
    "/{channel_id}/resend-code",
    [Scope.ME_WRITE],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def resend_notification_channel_code(request: Request, channel_id: int) -> None:
    await _as_http(channels.resend_code(_get_or_404(channel_id, request.user)))
