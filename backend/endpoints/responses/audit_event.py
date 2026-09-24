from typing import Any

from models.audit_event import (
    AuditAction,
    AuditActorKind,
    AuditCategory,
    AuditEvent,
    category_of,
)

from .base import BaseModel, UTCDatetime
from .notification import NotificationActorSchema


class AuditEventSchema(BaseModel):
    id: int
    # A row written under an action a later version dropped must still list.
    action: AuditAction | str
    category: AuditCategory | None
    occurred_at: UTCDatetime
    actor_kind: AuditActorKind | str
    # The account as it is now; null once it's deleted, when `actor_name` remains.
    actor: NotificationActorSchema | None
    actor_name: str | None
    target_type: str | None
    target_id: str | None
    target_name: str | None
    ip_address: str | None
    device_id: str | None
    device_name: str | None
    data: dict[str, Any]

    @classmethod
    def from_row(cls, event: AuditEvent, device_name: str | None) -> "AuditEventSchema":
        return cls(
            id=event.id,
            action=event.action,
            category=category_of(event.action),
            occurred_at=event.occurred_at,
            actor_kind=event.actor_kind,
            actor=(
                NotificationActorSchema.model_validate(event.actor)
                if event.actor
                else None
            ),
            actor_name=event.actor_name,
            target_type=event.target_type,
            target_id=event.target_id,
            target_name=event.target_name,
            ip_address=event.ip_address,
            device_id=event.device_id,
            device_name=device_name,
            data=event.data,
        )
