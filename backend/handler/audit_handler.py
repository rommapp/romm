"""The audit log: what users, or RomM itself, did, recorded once it succeeded.

Best effort: a failure to record is logged and never reaches the action.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Final

from starlette.requests import HTTPConnection

from config import AUDIT_LOG_RETENTION_DAYS
from handler.database import db_audit_event_handler, db_user_handler
from handler.redis_handler import sync_cache
from logger.logger import log
from models.audit_event import (
    AUDIT_DATA_MAX_LENGTH,
    AUDIT_NAME_MAX_LENGTH,
    AuditAction,
    AuditActorKind,
    AuditEvent,
    AuditTargetType,
)
from utils.datetime import to_utc

if TYPE_CHECKING:
    from models.collection import Collection, SmartCollection
    from models.firmware import Firmware
    from models.platform import Platform
    from models.rom import Rom, RomDeletionTarget, RomVisibilityLabel
    from models.user import User

# Lists in `data` (rom ids, changed fields) keep this many entries.
MAX_DATA_LIST_LENGTH: Final = 50
# A download repeated within this window, by the same caller, is the same download.
DOWNLOAD_DEDUPE_SECONDS: Final = 10 * 60
_CLAIM_KEY_PREFIX: Final = "romm:audit:once"
_RANGE_START = re.compile(r"^\s*bytes\s*=\s*(\d*)\s*-")


def _clip_name(name: str | None) -> str | None:
    if name is None:
        return None
    return name.replace("\x00", "")[:AUDIT_NAME_MAX_LENGTH]


@dataclass(frozen=True, slots=True)
class AuditActor:
    kind: AuditActorKind
    user_id: int | None = None
    name: str | None = None
    ip_address: str | None = None
    device_id: str | None = None

    @classmethod
    def from_request(cls, conn: HTTPConnection) -> AuditActor:
        """Whoever made the request, anonymous when no account is behind it."""
        user = conn.scope.get("user")
        ip_address = conn.client.host if conn.client else None
        device_id = getattr(conn.state, "device_id", None) or (
            conn.scope.get("session") or {}
        ).get("device_id")
        if (
            user is None
            or not user.is_authenticated
            or getattr(user, "is_kiosk_guest", False)
        ):
            return cls(AuditActorKind.ANONYMOUS, ip_address=ip_address)
        return cls(
            AuditActorKind.USER,
            user_id=user.id,
            name=user.username,
            ip_address=ip_address,
            device_id=device_id,
        )

    @classmethod
    def for_user(
        cls,
        user: User,
        *,
        ip_address: str | None = None,
        device_id: str | None = None,
    ) -> AuditActor:
        return cls(
            AuditActorKind.USER,
            user_id=user.id,
            name=user.username,
            ip_address=ip_address,
            device_id=device_id,
        )

    @classmethod
    def for_user_id(cls, user_id: int | None) -> AuditActor:
        """The user a background job ran for, or the system when nobody started it."""
        if user_id is None:
            return SYSTEM_ACTOR
        try:
            user = db_user_handler.get_user(user_id)
        except Exception:  # noqa: BLE001 - the name is a nicety
            user = None
        if user is None:
            return cls(AuditActorKind.USER)
        return cls.for_user(user)


SYSTEM_ACTOR: Final = AuditActor(AuditActorKind.SYSTEM)


@dataclass(frozen=True, slots=True)
class AuditTarget:
    type: AuditTargetType
    id: int | str | None
    name: str | None

    @classmethod
    def of_rom(cls, rom: Rom | RomVisibilityLabel | RomDeletionTarget) -> AuditTarget:
        return cls(AuditTargetType.ROM, rom.id, rom.name or rom.fs_name)

    @classmethod
    def of_platform(cls, platform: Platform) -> AuditTarget:
        return cls(
            AuditTargetType.PLATFORM,
            platform.id,
            platform.custom_name or platform.name,
        )

    @classmethod
    def of_collection(cls, collection: Collection) -> AuditTarget:
        return cls(AuditTargetType.COLLECTION, collection.id, collection.name)

    @classmethod
    def of_smart_collection(cls, collection: SmartCollection) -> AuditTarget:
        return cls(AuditTargetType.SMART_COLLECTION, collection.id, collection.name)

    @classmethod
    def of_firmware(cls, firmware: Firmware) -> AuditTarget:
        return cls(AuditTargetType.FIRMWARE, firmware.id, firmware.file_name)

    @classmethod
    def of_user(cls, user: User) -> AuditTarget:
        return cls(AuditTargetType.USER, user.id, user.username)


@dataclass(frozen=True, slots=True)
class AuditDraft:
    action: AuditAction
    actor: AuditActor
    target: AuditTarget | None = None
    data: dict[str, Any] | None = None
    occurred_at: datetime | None = None


def _encode(data: dict[str, Any]) -> str:
    # PostgreSQL refuses NUL in JSON text.
    return json.dumps(data, default=str).replace("\\u0000", "")


def _normalize_data(data: dict[str, Any] | None) -> dict[str, Any]:
    if not data:
        return {}
    clipped: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, (list, tuple, set, frozenset)):
            value = list(value)
            if len(value) > MAX_DATA_LIST_LENGTH:
                clipped["truncated"] = True
                value = value[:MAX_DATA_LIST_LENGTH]
        clipped[key] = value
    encoded = _encode(clipped)
    if len(encoded) > AUDIT_DATA_MAX_LENGTH:
        scalars = {k: v for k, v in clipped.items() if not isinstance(v, (list, dict))}
        encoded = _encode({**scalars, "truncated": True})
        if len(encoded) > AUDIT_DATA_MAX_LENGTH:
            return {"truncated": True}
    return json.loads(encoded)


def _to_row(draft: AuditDraft) -> AuditEvent:
    actor, target = draft.actor, draft.target
    return AuditEvent(
        occurred_at=to_utc(draft.occurred_at or datetime.now(timezone.utc)),
        actor_kind=actor.kind,
        actor_id=actor.user_id,
        actor_name=_clip_name(actor.name),
        action=draft.action,
        target_type=target.type if target else None,
        target_id=str(target.id) if target and target.id is not None else None,
        target_name=_clip_name(target.name) if target else None,
        ip_address=actor.ip_address[:45] if actor.ip_address else None,
        device_id=_clip_name(actor.device_id),
        data=_normalize_data(draft.data),
    )


def record_many(drafts: Sequence[AuditDraft]) -> None:
    """Store events, logging rather than raising when they can't be stored."""
    try:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=AUDIT_LOG_RETENTION_DAYS)
            if AUDIT_LOG_RETENTION_DAYS > 0
            else None
        )
        rows = [
            _to_row(draft)
            for draft in drafts
            if cutoff is None
            or draft.occurred_at is None
            or to_utc(draft.occurred_at) >= cutoff
        ]
        if rows:
            db_audit_event_handler.add_events(rows)
    except Exception:  # noqa: BLE001 - never fail the action being recorded
        log.exception(
            f"Failed to record audit events {[draft.action for draft in drafts]}"
        )


def record(
    action: AuditAction,
    actor: AuditActor,
    target: AuditTarget | None = None,
    data: dict[str, Any] | None = None,
    *,
    occurred_at: datetime | None = None,
) -> None:
    record_many([AuditDraft(action, actor, target, data, occurred_at)])


def claim_once(key: str, window_seconds: int) -> bool:
    """Whether this is the first claim on `key` within the window; True if Redis fails."""
    try:
        return bool(
            sync_cache.set(f"{_CLAIM_KEY_PREFIX}:{key}", 1, nx=True, ex=window_seconds)
        )
    except Exception:  # noqa: BLE001 - better a duplicate than a gap
        log.exception(f"Failed to claim audit key {key}")
        return True


def _starts_a_transfer(range_header: str | None) -> bool:
    """Whether a request fetches a file from its first byte, rather than resuming it."""
    if range_header is None:
        return True
    match = _RANGE_START.match(range_header)
    # An unparseable Range is ignored by the server, which sends the whole file.
    if match is None:
        return True
    # `bytes=-500` asks for the last 500 bytes, which is no start either.
    start = match.group(1)
    return start != "" and int(start) == 0


def record_download(
    conn: HTTPConnection,
    target: AuditTarget | None,
    dedupe_key: str,
    data: dict[str, Any] | None = None,
    *,
    action: AuditAction = AuditAction.ROM_DOWNLOAD,
) -> None:
    """Record a download once, however many range requests and retries it takes."""
    if conn.scope.get("method") != "GET" or not _starts_a_transfer(
        conn.headers.get("range")
    ):
        return
    actor = AuditActor.from_request(conn)
    caller = actor.user_id if actor.user_id is not None else actor.ip_address
    if not claim_once(f"download:{caller}:{dedupe_key}", DOWNLOAD_DEDUPE_SECONDS):
        return
    user_agent = conn.headers.get("user-agent")
    record(
        action,
        actor,
        target,
        {**(data or {}), "user_agent": user_agent[:255] if user_agent else None},
    )
