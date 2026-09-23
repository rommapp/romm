"""Forwarding stored notifications to their users' channels, one RQ job per channel."""

import asyncio
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any, Final

from rq import Retry, get_current_job

from endpoints.responses.notification import NotificationSchema
from handler.database import db_notification_channel_handler
from handler.email_handler import send_email
from handler.redis_handler import low_prio_queue
from logger.logger import log
from models.notification import NotificationKind, NotificationLevel, topic_of
from models.notification_channel import NotificationChannel, NotificationChannelType
from models.user import Role
from utils.secret_box import unseal

from . import webhook
from .config import WebhookConfig
from .messages import OutboundMessage, render

# Info and success both mean nothing needs doing.
_LEVEL_RANK: Final[dict[str, int]] = {
    NotificationLevel.INFO: 0,
    NotificationLevel.SUCCESS: 0,
    NotificationLevel.WARNING: 1,
    NotificationLevel.ERROR: 2,
}
_RETRY: Final = Retry(max=3, interval=[30, 120, 600])
_JOB_TIMEOUT_SECONDS: Final = 60


def may_reach_private_network(role: str) -> bool:
    """Whether a channel owned by someone with this role may reach the local network."""
    return role == Role.ADMIN


def describe_error(exc: Exception) -> str:
    return str(exc) or type(exc).__name__


def forwards(channel: NotificationChannel, notification: NotificationSchema) -> bool:
    """Whether the channel's level and topic filters let the notification through."""
    if _LEVEL_RANK.get(notification.level, 0) < _LEVEL_RANK.get(channel.min_level, 0):
        return False
    return channel.topics is None or topic_of(notification.kind) in channel.topics


def enqueue_channel_deliveries(
    stored: Sequence[tuple[int, NotificationSchema]],
) -> None:
    """Queue a delivery for each channel a stored notification goes out on.

    Args:
        stored: Each notification with the user it was stored for.
    """
    try:
        by_user: dict[int, list[NotificationChannel]] = defaultdict(list)
        for channel in db_notification_channel_handler.get_deliverable_channels(
            sorted({user_id for user_id, _ in stored})
        ):
            by_user[channel.user_id].append(channel)

        for user_id, notification in stored:
            wanted = [c for c in by_user[user_id] if forwards(c, notification)]
            if not wanted:
                continue
            payload = notification.model_dump(mode="json")
            for channel in wanted:
                low_prio_queue.enqueue(
                    deliver_to_channel,
                    kwargs={"channel_id": channel.id, "notification": payload},
                    retry=_RETRY,
                    job_timeout=_JOB_TIMEOUT_SECONDS,
                    result_ttl=0,
                    meta={"task_name": "Notification delivery"},
                )
    except Exception:  # noqa: BLE001 - the inbox already has it
        log.exception("Failed to queue notification channel deliveries")


async def send_to_channel(
    channel: NotificationChannel, message: OutboundMessage, allow_private: bool
) -> None:
    """Send one message out on a channel.

    Raises:
        UnsealError: ROMM_AUTH_SECRET_KEY changed since the channel was saved.
        WebhookError, EmailError: The delivery failed.
    """
    config = unseal(channel.config)
    if channel.type == NotificationChannelType.EMAIL:
        text = "\n\n".join(part for part in (message.body, message.url) if part)
        await asyncio.to_thread(
            send_email,
            config["address"],
            f"[RomM] {message.title}",
            text or message.title,
        )
    else:
        await webhook.send(
            WebhookConfig(
                url=config["url"], format=config["format"], secret=config.get("secret")
            ),
            message,
            allow_private=allow_private,
            channel_name=channel.name,
        )


def sample_message() -> OutboundMessage:
    """What a channel's test sends."""
    return render(
        NotificationSchema(
            id=0,
            kind=NotificationKind.CUSTOM,
            level=NotificationLevel.INFO,
            title="Test notification from RomM",
            body="If you can read this, the channel works.",
            link="/notifications",
            icon=None,
            data={},
            actor=None,
            read_at=None,
            created_at=datetime.now(timezone.utc),
        )
    )


def deliver_to_channel(channel_id: int, notification: dict[str, Any]) -> None:
    """RQ job: send a notification out on one channel, retrying a failure."""
    found = db_notification_channel_handler.get_channel_for_delivery(channel_id)
    if found is None:
        return
    channel, owner_role = found
    if not channel.enabled:
        return

    message = render(NotificationSchema.model_validate(notification))
    try:
        asyncio.run(
            send_to_channel(
                channel,
                message,
                allow_private=may_reach_private_network(owner_role),
            )
        )
    except Exception as exc:  # noqa: BLE001
        error = describe_error(exc)
        job = get_current_job()
        final = job is None or not job.retries_left
        db_notification_channel_handler.record_failure(channel_id, error, counts=final)
        # The last attempt returns, so no failed job is left behind.
        if not final:
            raise
        log.warning(f"Could not deliver notification to channel {channel_id}: {error}")
        if db_notification_channel_handler.turn_off_if_failing(channel_id):
            asyncio.run(_tell_owner_channel_is_off(channel, error))
        return

    db_notification_channel_handler.record_delivery(channel_id)


async def _tell_owner_channel_is_off(channel: NotificationChannel, error: str) -> None:
    # Imported here because the notification handler queues these deliveries.
    from handler.notification_handler import notify

    await notify(
        channel.user_id,
        NotificationKind.CHANNEL_DISABLED,
        NotificationLevel.WARNING,
        {"channel_id": channel.id, "name": channel.name, "error": error},
    )
