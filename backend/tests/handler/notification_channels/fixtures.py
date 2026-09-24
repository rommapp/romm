from datetime import datetime, timezone
from typing import Any

from endpoints.responses.notification import NotificationActorSchema, NotificationSchema
from models.notification import NotificationKind, NotificationLevel


def make_notification(**overrides: Any) -> NotificationSchema:
    fields: dict[str, Any] = {
        "id": 7,
        "kind": NotificationKind.CUSTOM,
        "level": NotificationLevel.INFO,
        "title": "Maintenance tonight",
        "body": "RomM restarts at 23:00",
        "link": "/platforms",
        "icon": None,
        "data": {},
        "actor": None,
        "read_at": None,
        "created_at": datetime(2026, 9, 23, 12, tzinfo=timezone.utc),
    }
    return NotificationSchema(**{**fields, **overrides})


def make_actor() -> NotificationActorSchema:
    return NotificationActorSchema(
        id=1,
        username="admin",
        avatar_path="",
        updated_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
    )
