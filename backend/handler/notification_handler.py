"""Persistent per-user notifications, stored first and then pushed to open tabs.

Every entry point swallows its own failures: the caller is usually a job whose
outcome must not hinge on reporting it.
"""

from typing import Any

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


async def notify(
    user_id: int,
    kind: NotificationKind,
    level: NotificationLevel,
    data: dict[str, Any] | None = None,
    actor_id: int | None = None,
) -> None:
    """Store a notification for one user and push it to their open tabs."""
    try:
        notification = db_notification_handler.add_notification(
            Notification(
                user_id=user_id,
                actor_id=actor_id,
                kind=kind,
                level=level,
                data=data or {},
            )
        )
        payload = NotificationSchema.model_validate(notification).model_dump(
            mode="json"
        )
    except Exception:  # noqa: BLE001
        log.exception(f"Failed to store {kind} notification for user {user_id}")
        return

    await emit_to_user(user_id, NOTIFICATIONS_NEW_EVENT, payload)


async def notify_admins(
    kind: NotificationKind,
    level: NotificationLevel,
    data: dict[str, Any] | None = None,
) -> None:
    """Notify every enabled admin, for what the system did on nobody's behalf."""
    try:
        admins = db_user_handler.get_admin_users()
    except Exception:  # noqa: BLE001
        log.exception(f"Failed to look up the admins to notify of {kind}")
        return

    for admin in admins:
        if admin.enabled:
            await notify(admin.id, kind, level, data)
