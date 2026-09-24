"""The audit log: what users and background jobs did, recorded best effort."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
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
from models.collection import Collection, SmartCollection
from utils.auth import current_device_id
from utils.datetime import to_utc
from utils.rate_limit import count_in_window

if TYPE_CHECKING:
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


def client_ip(conn: HTTPConnection) -> str | None:
    return conn.client.host if conn.client else None


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
        if (
            user is None
            or not user.is_authenticated
            or getattr(user, "is_kiosk_guest", False)
        ):
            return cls.anonymous(client_ip(conn))
        return cls.for_user(
            user, ip_address=client_ip(conn), device_id=current_device_id(conn)
        )

    @classmethod
    def anonymous(cls, ip_address: str | None) -> AuditActor:
        return cls(AuditActorKind.ANONYMOUS, ip_address=ip_address)

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
    def of_collection(cls, collection: Collection | SmartCollection) -> AuditTarget:
        kind = (
            AuditTargetType.SMART_COLLECTION
            if isinstance(collection, SmartCollection)
            else AuditTargetType.COLLECTION
        )
        return cls(kind, collection.id, collection.name)

    @classmethod
    def of_firmware(cls, firmware: Firmware) -> AuditTarget:
        return cls(AuditTargetType.FIRMWARE, firmware.id, firmware.file_name)

    @classmethod
    def of_user(cls, user: User) -> AuditTarget:
        return cls(AuditTargetType.USER, user.id, user.username)


# A target that takes a lookup to name can be passed as a function, so the
# lookup runs inside the recorder's error handling, and only if it records.
TargetSource = AuditTarget | Callable[[], AuditTarget | None] | None


@dataclass(frozen=True, slots=True)
class AuditDraft:
    action: AuditAction
    actor: AuditActor
    target: TargetSource = None
    data: dict[str, Any] | None = None
    occurred_at: datetime | None = None


def _unset(value: Any) -> Any:
    # A save writes "" over a column that was null, which is no change.
    return None if value == "" else value


def _value(source: object, field: str) -> Any:
    if isinstance(source, Mapping):
        return _unset(source.get(field))
    return _unset(getattr(source, field, None))


def changed_fields(before: object, after: object, fields: Iterable[str]) -> list[str]:
    """The fields whose value differs; `after` may be a mapping of the fields given."""
    return [
        field
        for field in fields
        if (not isinstance(after, Mapping) or field in after)
        and _value(before, field) != _value(after, field)
    ]


def change(before: object, after: object, field: str) -> dict[str, Any]:
    """One field's change, in the shape the event log reads it."""
    return {"from": _value(before, field), "to": _value(after, field)}


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
    actor = draft.actor
    target = draft.target() if callable(draft.target) else draft.target
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
    actor: AuditActor | HTTPConnection,
    target: TargetSource = None,
    data: dict[str, Any] | None = None,
    *,
    occurred_at: datetime | None = None,
) -> None:
    """Record one event; `actor` may be the request, whose caller then acts."""
    if isinstance(actor, HTTPConnection):
        actor = AuditActor.from_request(actor)
    record_many([AuditDraft(action, actor, target, data, occurred_at)])


def _claim_key(key: str) -> str:
    # Keys carry caller-supplied text (usernames, file ids), so they're hashed to
    # a fixed size.
    return f"{_CLAIM_KEY_PREFIX}:{hashlib.sha256(key.encode()).hexdigest()}"


def claim_once(key: str, window_seconds: int) -> bool:
    """Whether this is the first claim on `key` within the window; True if Redis fails."""
    try:
        return bool(sync_cache.set(_claim_key(key), 1, nx=True, ex=window_seconds))
    except Exception:  # noqa: BLE001 - better a duplicate than a gap
        # The key may hold a failed sign-in's text, so only its kind is logged.
        log.exception(f"Failed to claim a {key.split(':', 1)[0]} audit key")
        return True


def within_budget(key: str, limit: int, window_seconds: int) -> bool:
    """Whether `key` has been counted at most `limit` times this window; True if Redis fails."""
    try:
        return count_in_window(_claim_key(key), window_seconds) <= limit
    except Exception:  # noqa: BLE001 - better a duplicate than a gap
        log.exception(f"Failed to count a {key.split(':', 1)[0]} audit key")
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
    return start != "" and start.strip("0") == ""


def record_download(
    conn: HTTPConnection,
    target: TargetSource,
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
