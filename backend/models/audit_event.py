from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any, Final

from sqlalchemy import TIMESTAMP, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel, utc_now
from utils.database import CustomJSON

if TYPE_CHECKING:
    from models.user import User


class AuditAction(enum.StrEnum):
    """What a user, or RomM itself, did; the client builds its sentence from `data`."""

    ROM_DOWNLOAD = "rom.download"
    ROM_BULK_DOWNLOAD = "rom.bulk_download"
    ROM_PLAY = "rom.play"

    ROM_UPLOAD = "rom.upload"
    ROM_CREATE = "rom.create"
    ROM_EDIT = "rom.edit"
    ROM_MATCH = "rom.match"
    ROM_UNMATCH = "rom.unmatch"
    ROM_DELETE = "rom.delete"
    ROM_FILE_DELETE = "rom.file_delete"
    PLATFORM_CREATE = "platform.create"
    PLATFORM_EDIT = "platform.edit"
    PLATFORM_DELETE = "platform.delete"
    FIRMWARE_UPLOAD = "firmware.upload"
    FIRMWARE_DELETE = "firmware.delete"
    CONFIG_UPDATE = "config.update"

    COLLECTION_CREATE = "collection.create"
    COLLECTION_EDIT = "collection.edit"
    COLLECTION_DELETE = "collection.delete"
    COLLECTION_ADD_ROMS = "collection.add_roms"
    COLLECTION_REMOVE_ROMS = "collection.remove_roms"
    SMART_COLLECTION_CREATE = "smart_collection.create"
    SMART_COLLECTION_EDIT = "smart_collection.edit"
    SMART_COLLECTION_DELETE = "smart_collection.delete"

    SCAN_START = "scan.start"
    SCAN_FINISH = "scan.finish"
    SCAN_STOP = "scan.stop"
    TASK_RUN = "task.run"

    AUTH_LOGIN = "auth.login"
    AUTH_LOGIN_FAILED = "auth.login_failed"
    AUTH_PASSWORD_RESET_REQUEST = "auth.password_reset_request"
    AUTH_PASSWORD_RESET = "auth.password_reset"
    USER_CREATE = "user.create"
    USER_REGISTER = "user.register"
    USER_EDIT = "user.edit"
    USER_DELETE = "user.delete"
    USER_PERMISSIONS_EDIT = "user.permissions_edit"
    PERMISSION_GROUP_CREATE = "permission_group.create"
    PERMISSION_GROUP_EDIT = "permission_group.edit"
    PERMISSION_GROUP_DELETE = "permission_group.delete"
    VISIBILITY_HIDE = "visibility.hide"
    VISIBILITY_UNHIDE = "visibility.unhide"
    CLIENT_TOKEN_CREATE = "client_token.create"
    CLIENT_TOKEN_REGENERATE = "client_token.regenerate"
    CLIENT_TOKEN_REVOKE = "client_token.revoke"
    DEVICE_APPROVE = "device.approve"


class AuditCategory(enum.StrEnum):
    CONSUMPTION = "consumption"
    LIBRARY = "library"
    COLLECTIONS = "collections"
    OPERATIONS = "operations"
    SECURITY = "security"


class AuditActorKind(enum.StrEnum):
    USER = "user"
    # Someone with no account behind them: a kiosk visitor, an unauthenticated
    # download, a login attempt for a username that doesn't exist.
    ANONYMOUS = "anonymous"
    # A scheduled job or the filesystem watcher.
    SYSTEM = "system"


class AuditTargetType(enum.StrEnum):
    ROM = "rom"
    PLATFORM = "platform"
    FIRMWARE = "firmware"
    COLLECTION = "collection"
    SMART_COLLECTION = "smart_collection"
    VIRTUAL_COLLECTION = "virtual_collection"
    USER = "user"
    PERMISSION_GROUP = "permission_group"
    CLIENT_TOKEN = "client_token"
    DEVICE = "device"
    TASK = "task"
    CONFIG = "config"


_CATEGORY_PREFIXES: Final[dict[str, AuditCategory]] = {
    "rom": AuditCategory.LIBRARY,
    "platform": AuditCategory.LIBRARY,
    "firmware": AuditCategory.LIBRARY,
    "config": AuditCategory.LIBRARY,
    "collection": AuditCategory.COLLECTIONS,
    "smart_collection": AuditCategory.COLLECTIONS,
    "scan": AuditCategory.OPERATIONS,
    "task": AuditCategory.OPERATIONS,
    "auth": AuditCategory.SECURITY,
    "user": AuditCategory.SECURITY,
    "permission_group": AuditCategory.SECURITY,
    "visibility": AuditCategory.SECURITY,
    "client_token": AuditCategory.SECURITY,
    "device": AuditCategory.SECURITY,
}

_CONSUMPTION_ACTIONS: Final = frozenset(
    {AuditAction.ROM_DOWNLOAD, AuditAction.ROM_BULK_DOWNLOAD, AuditAction.ROM_PLAY}
)


def category_of(action: str) -> AuditCategory | None:
    """The group an action is filtered under; None for one RomM no longer defines."""
    if action in _CONSUMPTION_ACTIONS:
        return AuditCategory.CONSUMPTION
    return _CATEGORY_PREFIXES.get(action.partition(".")[0])


def actions_in(category: AuditCategory) -> list[AuditAction]:
    return [action for action in AuditAction if category_of(action) == category]


AUDIT_NAME_MAX_LENGTH: Final = 255
AUDIT_ACTION_MAX_LENGTH: Final = 64
# Cap on `data` as serialized JSON; longer lists are clipped before this applies.
AUDIT_DATA_MAX_LENGTH: Final = 4096


class AuditEvent(BaseModel):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_occurred_at", "occurred_at"),
        # Leads with `actor_id`, so it also backs that foreign key.
        Index("ix_audit_events_actor_occurred", "actor_id", "occurred_at"),
        Index("ix_audit_events_target", "target_type", "target_id", "occurred_at"),
        Index("ix_audit_events_action_occurred", "action", "occurred_at"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # When it happened, which for a play session reported later is its start.
    occurred_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=utc_now
    )
    actor_kind: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Names are copied in so an event still reads after its user or target is gone.
    actor_name: Mapped[str | None] = mapped_column(
        String(AUDIT_NAME_MAX_LENGTH), nullable=True
    )
    action: Mapped[str] = mapped_column(String(AUDIT_ACTION_MAX_LENGTH))
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # A string with no foreign key: device and task ids aren't integers, and
    # targets get deleted.
    target_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_name: Mapped[str | None] = mapped_column(
        String(AUDIT_NAME_MAX_LENGTH), nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(CustomJSON(), default=dict)

    actor: Mapped[User | None] = relationship(lazy="raise", foreign_keys=[actor_id])
