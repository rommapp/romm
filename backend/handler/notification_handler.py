"""Persistent per-user notifications, stored first and then pushed to open tabs."""

from collections.abc import Sequence
from typing import Any, Literal

from endpoints.responses.notification import NotificationSchema
from handler.database import db_notification_handler, db_user_handler
from handler.socket_handler import socket_handler
from logger.logger import log
from models.notification import Notification, NotificationKind, NotificationLevel
from models.user import Role, User

NOTIFICATIONS_NEW_EVENT = "notifications:new"
NOTIFICATIONS_READ_EVENT = "notifications:read"
NOTIFICATIONS_DISMISSED_EVENT = "notifications:dismissed"


async def deliver(notifications: Sequence[Notification]) -> list[NotificationSchema]:
    """Store notifications in one transaction, then push each to its user's open tabs.

    Raises if they can't be stored.
    """
    stored = [
        (row.user_id, NotificationSchema.model_validate(row))
        for row in db_notification_handler.add_notifications(notifications)
    ]
    # One after another: concurrent publishes would each open a Redis connection.
    for user_id, schema in stored:
        await socket_handler.emit_to_user(
            user_id, NOTIFICATIONS_NEW_EVENT, schema.model_dump(mode="json")
        )
    return [schema for _, schema in stored]


class UnknownRecipientsError(ValueError):
    """Some of the users a notification names are missing or disabled."""

    def __init__(self, user_ids: set[int]) -> None:
        self.user_ids = user_ids
        super().__init__(
            f"No enabled user with id {', '.join(map(str, sorted(user_ids)))}"
        )


def recipient_ids(recipients: Sequence[int] | Literal["admins", "all"]) -> list[int]:
    """The enabled users among the given ids, or among every admin or user."""
    users = db_user_handler.get_users(
        roles=[Role.ADMIN] if recipients == "admins" else (),
        only_fields=[User.id, User.enabled],
    )
    enabled = [user.id for user in users if user.enabled]
    if isinstance(recipients, str):
        return enabled
    wanted = set(recipients)
    return [user_id for user_id in enabled if user_id in wanted]


def resolve_recipients(
    sender_id: int, recipients: Sequence[int] | Literal["admins", "all"] | None
) -> list[int]:
    """Who a notification sent by `sender_id` reaches; None means the sender.

    Raises:
        UnknownRecipientsError: A named user is missing or disabled.
    """
    if recipients is None:
        return [sender_id]
    if isinstance(recipients, str):
        return recipient_ids(recipients)
    if list(recipients) == [sender_id]:
        return [sender_id]
    user_ids = recipient_ids(recipients)
    missing = set(recipients) - set(user_ids)
    if missing:
        raise UnknownRecipientsError(missing)
    return user_ids


async def send(
    sender_id: int,
    user_ids: Sequence[int],
    kind: NotificationKind | str,
    level: NotificationLevel,
    data: dict[str, Any],
    *,
    title: str | None,
    body: str | None,
    link: str | None,
    icon: str | None,
) -> list[NotificationSchema]:
    """Deliver a user's notification, naming them as its sender to everyone else.

    Raises if it can't be stored, unlike `notify`.
    """
    return await deliver(
        [
            Notification(
                user_id=user_id,
                actor_id=sender_id if user_id != sender_id else None,
                kind=kind,
                level=level,
                title=title,
                body=body,
                link=link,
                icon=icon,
                data=data,
            )
            for user_id in user_ids
        ]
    )


async def _notify_all(
    user_ids: Sequence[int],
    kind: NotificationKind | str,
    level: NotificationLevel,
    data: dict[str, Any] | None,
    actor_id: int | None,
    content: dict[str, str | None],
) -> None:
    if not user_ids:
        return
    try:
        await deliver(
            [
                Notification(
                    user_id=user_id,
                    actor_id=actor_id,
                    kind=kind,
                    level=level,
                    data=data or {},
                    **content,
                )
                for user_id in user_ids
            ]
        )
    except Exception:  # noqa: BLE001 - never fail the job that is reporting
        log.exception(f"Failed to store {kind} notification for users {user_ids}")


async def notify(
    user_id: int,
    kind: NotificationKind | str,
    level: NotificationLevel,
    data: dict[str, Any] | None = None,
    actor_id: int | None = None,
    *,
    title: str | None = None,
    body: str | None = None,
    link: str | None = None,
    icon: str | None = None,
) -> None:
    """Notify one user, logging rather than raising a failure to store it.

    Args:
        kind: A `NotificationKind` is translated from `data`; any other shows
            `title`, `body`, `link` (an in-app path) and `icon`.
    """
    content = {"title": title, "body": body, "link": link, "icon": icon}
    await _notify_all([user_id], kind, level, data, actor_id, content)


async def notify_admins(
    kind: NotificationKind | str,
    level: NotificationLevel,
    data: dict[str, Any] | None = None,
    *,
    title: str | None = None,
    body: str | None = None,
    link: str | None = None,
    icon: str | None = None,
) -> None:
    """Notify every enabled admin of what the system did on nobody's behalf."""
    try:
        admin_ids = recipient_ids("admins")
    except Exception:  # noqa: BLE001
        log.exception(f"Failed to look up the admins to notify of {kind}")
        return
    content = {"title": title, "body": body, "link": link, "icon": icon}
    await _notify_all(admin_ids, kind, level, data, None, content)


async def notify_user_or_admins(
    user_id: int | None,
    kind: NotificationKind,
    level: NotificationLevel,
    data: dict[str, Any],
    *,
    admins_too: bool,
) -> None:
    """Notify whoever started a job, or the admins when nobody did and `admins_too`."""
    if user_id is not None:
        await notify(user_id, kind, level, data)
    elif admins_too:
        await notify_admins(kind, level, data)
