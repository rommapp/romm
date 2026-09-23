from fastapi import HTTPException, Request, status

from decorators.auth import protected_route
from endpoints.responses.notification import NotificationIdsPayload, NotificationSchema
from handler.auth.constants import Scope
from handler.database import db_notification_handler
from handler.notification_handler import (
    NOTIFICATIONS_DISMISSED_EVENT,
    NOTIFICATIONS_READ_EVENT,
    emit_to_user,
)
from utils.router import APIRouter

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
)


@protected_route(router.get, "", [Scope.ME_READ])
def get_notifications(request: Request) -> list[NotificationSchema]:
    """The caller's notifications, newest first."""
    return [
        NotificationSchema.model_validate(n)
        for n in db_notification_handler.get_notifications(request.user.id)
    ]


@protected_route(router.post, "/read", [Scope.ME_WRITE])
async def mark_notifications_read(
    request: Request, payload: NotificationIdsPayload
) -> None:
    """Mark the given notifications read, or all of them when `ids` is null."""
    db_notification_handler.mark_read(request.user.id, payload.ids)
    await emit_to_user(request.user.id, NOTIFICATIONS_READ_EVENT, {"ids": payload.ids})


@protected_route(router.delete, "/{notification_id}", [Scope.ME_WRITE])
async def dismiss_notification(request: Request, notification_id: int) -> None:
    rows = db_notification_handler.delete_notifications(
        request.user.id, [notification_id]
    )
    if rows == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    await emit_to_user(
        request.user.id, NOTIFICATIONS_DISMISSED_EVENT, {"ids": [notification_id]}
    )


@protected_route(router.delete, "", [Scope.ME_WRITE])
async def dismiss_all_notifications(request: Request) -> None:
    db_notification_handler.delete_notifications(request.user.id)
    await emit_to_user(request.user.id, NOTIFICATIONS_DISMISSED_EVENT, {"ids": None})
