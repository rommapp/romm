"""Adding, changing, testing and confirming a user's notification channels."""

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from config import EMAIL_ENABLED
from handler.database import db_notification_channel_handler
from models.notification import NotificationLevel, NotificationTopic
from models.notification_channel import (
    MAX_NOTIFICATION_CHANNELS_PER_USER,
    NotificationChannel,
    NotificationChannelType,
    WebhookFormat,
)
from models.user import Role, User

from .config import EmailConfig, WebhookConfig, read_config, seal_config
from .confirmation import check_code, issue_code
from .delivery import sample_message, send_to_channel
from .webhook import check_url


class ChannelError(ValueError):
    """A change the channel can't take, worded for the user."""


def _may_reach_private_network(user: User) -> bool:
    return user.role == Role.ADMIN


def _check_webhook(url: str, format: WebhookFormat, user: User) -> None:
    try:
        check_url(url, format, allow_private=_may_reach_private_network(user))
    except ValueError as exc:
        raise ChannelError(str(exc)) from exc


def _require_email() -> None:
    if not EMAIL_ENABLED:
        raise ChannelError("Email isn't set up on this server")


async def create_channel(
    user: User,
    type: NotificationChannelType,
    name: str,
    min_level: NotificationLevel,
    topics: Sequence[NotificationTopic] | None,
    *,
    url: str | None = None,
    format: WebhookFormat = WebhookFormat.JSON,
    secret: str | None = None,
    address: str | None = None,
) -> NotificationChannel:
    """Add a channel; an email address gets a code to confirm it with first.

    Raises:
        ChannelError: The channel can't be added as asked.
        CodeCooldownError, EmailError: The confirmation code could not go out,
            in which case the channel is not kept.
    """
    if (
        db_notification_channel_handler.count_channels(user.id)
        >= MAX_NOTIFICATION_CHANNELS_PER_USER
    ):
        raise ChannelError(
            f"A user can have at most {MAX_NOTIFICATION_CHANNELS_PER_USER} channels"
        )

    config: WebhookConfig | EmailConfig
    if type == NotificationChannelType.EMAIL:
        _require_email()
        if not address:
            raise ChannelError("An email channel needs an address")
        config = EmailConfig(address=address)
        confirmed_at = None
    else:
        if not url:
            raise ChannelError("A webhook needs a URL")
        _check_webhook(url, format, user)
        config = WebhookConfig(url=url, format=format, secret=secret or None)
        confirmed_at = datetime.now(timezone.utc)

    channel = db_notification_channel_handler.add_channel(
        NotificationChannel(
            user_id=user.id,
            type=type,
            name=name,
            config=seal_config(config),
            min_level=min_level,
            topics=list(topics) if topics is not None else None,
            enabled=True,
            confirmed_at=confirmed_at,
            consecutive_failures=0,
        )
    )

    if address and type == NotificationChannelType.EMAIL:
        try:
            await issue_code(channel.id, address)
        except Exception:
            db_notification_channel_handler.delete_channel(channel.id, user.id)
            raise
    return channel


async def update_channel(
    channel: NotificationChannel,
    user: User,
    changes: dict[str, Any],
    *,
    url: str | None = None,
    format: WebhookFormat | None = None,
    secret: str | None = None,
    secret_given: bool = False,
    address: str | None = None,
) -> NotificationChannel:
    """Change a channel; a new email address has to be confirmed again.

    Args:
        changes: New values for the name, `enabled`, `min_level` and `topics`.
        secret_given: Whether `secret` was sent, since an empty one drops it.

    Raises:
        ChannelError: The change can't be made as asked.
        CodeCooldownError, EmailError: The code for a new address could not go out.
    """
    changes = dict(changes)
    if changes.get("enabled") and not channel.enabled:
        # Turning it back on starts its failure count afresh.
        changes["consecutive_failures"] = 0

    config = read_config(channel.config)
    new_address: str | None = None
    if channel.type == NotificationChannelType.EMAIL:
        if address and address != config.get("address"):
            _require_email()
            new_address = address
            changes["config"] = seal_config(EmailConfig(address=address))
            changes["confirmed_at"] = None
    elif url or format or secret_given:
        new_url = url or config.get("url")
        new_format = WebhookFormat(format or config.get("format") or WebhookFormat.JSON)
        if not new_url:
            raise ChannelError("The channel needs its URL again")
        _check_webhook(new_url, new_format, user)
        changes["config"] = seal_config(
            WebhookConfig(
                url=new_url,
                format=new_format,
                secret=(secret or None) if secret_given else config.get("secret"),
            )
        )

    updated = (
        db_notification_channel_handler.update_channel(channel.id, user.id, changes)
        if changes
        else channel
    )
    if new_address:
        await issue_code(channel.id, new_address)
    return updated or channel


async def send_sample(channel: NotificationChannel, user: User) -> str | None:
    """Send a sample notification out on the channel; returns why it failed, if it did.

    Raises:
        ChannelError: The channel's email address isn't confirmed yet.
    """
    if channel.confirmed_at is None:
        raise ChannelError("Confirm the email address first")
    try:
        await send_to_channel(
            channel,
            sample_message(),
            allow_private=_may_reach_private_network(user),
        )
    except Exception as exc:  # noqa: BLE001 - the error goes back to the user
        error = str(exc) or type(exc).__name__
        db_notification_channel_handler.record_failure(channel.id, error, counts=False)
        return error
    db_notification_channel_handler.record_delivery(channel.id)
    return None


async def confirm_channel(
    channel: NotificationChannel, user: User, code: str
) -> NotificationChannel:
    """Confirm an email address with the code sent to it.

    Raises:
        ChannelError: The code is wrong, spent or expired.
    """
    if channel.confirmed_at is not None:
        return channel
    if not await check_code(channel.id, code):
        raise ChannelError("That code is wrong or has expired")
    return (
        db_notification_channel_handler.update_channel(
            channel.id, user.id, {"confirmed_at": datetime.now(timezone.utc)}
        )
        or channel
    )


async def resend_code(channel: NotificationChannel) -> None:
    """Email the unconfirmed address a new code.

    Raises:
        ChannelError: The channel needs no code, or has lost its address.
        CodeCooldownError, EmailError: The code could not go out.
    """
    if channel.type != NotificationChannelType.EMAIL or channel.confirmed_at:
        raise ChannelError("The channel needs no confirmation")
    _require_email()
    address = read_config(channel.config).get("address")
    if not address:
        raise ChannelError("The channel needs its address again")
    await issue_code(channel.id, address)
