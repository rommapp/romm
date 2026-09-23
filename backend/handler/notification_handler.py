"""Persistent per-user notifications, stored first and then pushed to open tabs.

`notify` and `notify_admins` swallow their own failures: the caller is usually
a job whose outcome must not hinge on reporting it.
"""

from collections.abc import Sequence
from typing import Any, Literal

import socketio

from config import REDIS_URL
from endpoints.responses.notification import NotificationSchema
from handler.database import db_notification_handler, db_user_handler
from logger.logger import log
from models.notification import Notification, NotificationKind, NotificationLevel

NOTIFICATIONS_NEW_EVENT = "notifications:new"
NOTIFICATIONS_READ_EVENT = "notifications:read"
NOTIFICATIONS_DISMISSED_EVENT = "notifications:dismissed"


async def emit_to_user(user_id: int, event: str, payload: dict[str, Any]) -> None:
    """Push an event to every open tab of one user, from the web process or a worker."""
    try:
        manager = socketio.AsyncRedisManager(REDIS_URL, write_only=True)
        await manager.emit(event, payload, room=f"user:{user_id}")
    except Exception:  # noqa: BLE001
        log.warning(f"Failed to push {event} to user {user_id}", exc_info=True)


async def deliver(notification: Notification) -> NotificationSchema:
    """Store a notification and push it to its user's open tabs; raises if it can't be stored."""
    stored = NotificationSchema.model_validate(
        db_notification_handler.add_notification(notification)
    )
    await emit_to_user(
        notification.user_id, NOTIFICATIONS_NEW_EVENT, stored.model_dump(mode="json")
    )
    return stored


def recipient_ids(recipients: Sequence[int] | Literal["admins", "all"]) -> list[int]:
    """The enabled users among the given ids, or among every admin or user."""
    if recipients == "admins":
        users = list(db_user_handler.get_admin_users())
    elif recipients == "all":
        users = list(db_user_handler.get_users())
    else:
        users = [
            user
            for user_id in dict.fromkeys(recipients)
            if (user := db_user_handler.get_user(user_id))
        ]
    return [user.id for user in users if user.enabled]


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
    """Notify one user.

    A kind RomM's client knows is shown translated from `data`; any other, like
    `custom`, is shown with `title`, `body`, `link` (an in-app path) and `icon`.
    """
    try:
        await deliver(
            Notification(
                user_id=user_id,
                actor_id=actor_id,
                kind=kind,
                level=level,
                title=title,
                body=body,
                link=link,
                icon=icon,
                data=data or {},
            )
        )
    except Exception:  # noqa: BLE001
        log.exception(f"Failed to store {kind} notification for user {user_id}")


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
    """Notify every enabled admin, for what the system did on nobody's behalf."""
    try:
        admin_ids = recipient_ids("admins")
    except Exception:  # noqa: BLE001
        log.exception(f"Failed to look up the admins to notify of {kind}")
        return

    for admin_id in admin_ids:
        await notify(
            admin_id, kind, level, data, title=title, body=body, link=link, icon=icon
        )
