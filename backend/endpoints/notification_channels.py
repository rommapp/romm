from collections.abc import Awaitable
from functools import cache
from typing import TypeVar

from fastapi import HTTPException, Request, status

from decorators.auth import protected_route
from endpoints.responses.notification_channel import (
    AppriseServiceSchema,
    AppriseUrlFieldsSchema,
    AppriseUrlPayload,
    NotificationChannelCodePayload,
    NotificationChannelCreatePayload,
    NotificationChannelSchema,
    NotificationChannelTestResult,
    NotificationChannelUpdatePayload,
)
from handler.auth.constants import Scope
from handler.auth.dependencies import assert_admin
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


@protected_route(
    router.get,
    "/apprise-services",
    [Scope.ME_READ],
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "The caller is not an admin."},
    },
)
def get_apprise_services(request: Request) -> list[AppriseServiceSchema]:
    """Every service an admin's Apprise channel can go out on, with its fields."""
    assert_admin(request)
    return _apprise_catalog()


@protected_route(
    router.post,
    "/apprise-services/parse",
    [Scope.ME_READ],
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": (
                "Apprise cannot read the URL, or the URL is for a service RomM does"
                " not offer."
            )
        },
        status.HTTP_403_FORBIDDEN: {"description": "The caller is not an admin."},
    },
)
def parse_apprise_url(
    request: Request, payload: AppriseUrlPayload
) -> AppriseUrlFieldsSchema:
    """Read a service's own URL (a Discord webhook's) or an Apprise URL into its fields."""
    assert_admin(request)
    try:
        service, fields = apprise_channel.fields_from_url(payload.url)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return AppriseUrlFieldsSchema(service=service.id, fields=fields)


@cache
def _apprise_catalog() -> list[AppriseServiceSchema]:
    return [AppriseServiceSchema.from_service(s) for s in apprise_channel.services()]


@protected_route(
    router.post,
    "",
    [Scope.ME_WRITE],
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": (
                "The channel's target is missing or invalid, email is not set up on"
                " the server, a caller who is not an admin asks for an Apprise"
                " channel, or the caller already has the maximum number of channels."
            )
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "description": (
                "A confirmation code went to the caller or to this address less than"
                " a minute ago."
            )
        },
        status.HTTP_502_BAD_GATEWAY: {
            "description": "The mail server could not send the confirmation code."
        },
    },
)
async def create_notification_channel(
    request: Request, payload: NotificationChannelCreatePayload
) -> NotificationChannelSchema:
    """Add a channel; an email address gets a code to confirm it with first."""
    # What each type sends it to: a URL and secret, an address, or a service's fields.
    target = payload.model_dump(exclude={"type", "name", "min_level", "topics"})
    created = channels.create_channel(
        request.user,
        NotificationChannelType(payload.type),
        payload.name,
        payload.min_level,
        payload.topics,
        **target,
    )
    return NotificationChannelSchema.from_channel(await _as_http(created))


@protected_route(
    router.patch,
    "/{channel_id}",
    [Scope.ME_WRITE],
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": (
                "The new target is invalid, a new email address is given but email"
                " is not set up on the server, a caller who is not an admin edits an"
                " Apprise channel, or a webhook's URL changes to another origin and"
                " the request does not send its secret again."
            )
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "The caller has no notification channel with this ID."
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "description": (
                "A confirmation code went to the caller or to this address less than"
                " a minute ago."
            )
        },
        status.HTTP_502_BAD_GATEWAY: {
            "description": "The mail server could not send the confirmation code."
        },
    },
)
async def update_notification_channel(
    request: Request,
    channel_id: int,
    payload: NotificationChannelUpdatePayload,
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


@protected_route(
    router.delete,
    "/{channel_id}",
    [Scope.ME_WRITE],
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "The caller has no notification channel with this ID."
        }
    },
)
def delete_notification_channel(request: Request, channel_id: int) -> None:
    """Delete one of the caller's notification channels."""
    if not db_notification_channel_handler.delete_channel(channel_id, request.user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification channel not found",
        )


@protected_route(
    router.post,
    "/{channel_id}/test",
    [Scope.ME_WRITE],
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "The channel's email address is not confirmed yet."
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "The caller has no notification channel with this ID."
        },
    },
)
async def test_notification_channel(
    request: Request, channel_id: int
) -> NotificationChannelTestResult:
    """Send a sample notification out on the channel right away."""
    channel = _get_or_404(channel_id, request.user)
    try:
        error = await channels.send_sample(channel, request.user)
    except ChannelError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return NotificationChannelTestResult(ok=error is None, error=error)


@protected_route(
    router.post,
    "/{channel_id}/confirm",
    [Scope.ME_WRITE],
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": (
                "The code is wrong or has expired, or the channel has had too many"
                " wrong attempts."
            )
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "The caller has no notification channel with this ID."
        },
    },
)
async def confirm_notification_channel(
    request: Request,
    channel_id: int,
    payload: NotificationChannelCodePayload,
) -> NotificationChannelSchema:
    """Confirm an email address with the code sent to it."""
    channel = _get_or_404(channel_id, request.user)
    try:
        confirmed = await channels.confirm_channel(channel, request.user, payload.code)
    except ChannelError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return NotificationChannelSchema.from_channel(confirmed)


@protected_route(
    router.post,
    "/{channel_id}/resend-code",
    [Scope.ME_WRITE],
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": (
                "The channel is not an unconfirmed email channel, the channel has no"
                " email address, or email is not set up on the server."
            )
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "The caller has no notification channel with this ID."
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "description": (
                "A confirmation code went to the caller or to this address less than"
                " a minute ago."
            )
        },
        status.HTTP_502_BAD_GATEWAY: {
            "description": "The mail server could not send the confirmation code."
        },
    },
)
async def resend_notification_channel_code(request: Request, channel_id: int) -> None:
    """Send a new confirmation code to the channel's email address."""
    await _as_http(channels.resend_code(_get_or_404(channel_id, request.user)))
