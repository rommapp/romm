from datetime import datetime, timedelta, timezone
from typing import Any, Literal, NotRequired, TypedDict

from pydash import compact

from handler.audit_handler import AuditActor, AuditDraft, AuditTarget, record_many
from handler.auth.permissions import ResolvedPermissions
from handler.database import db_device_handler, db_play_session_handler, db_rom_handler
from logger.logger import log
from models.audit_event import AuditAction, AuditActorKind
from models.play_session import PlaySession
from models.rom import RomUserStatus
from utils.datetime import to_utc


class PlaySessionIngestResult(TypedDict):
    index: int
    status: Literal["created", "duplicate", "error"]
    id: NotRequired[int | None]
    detail: NotRequired[str | None]


class PlaySessionIngestSummary(TypedDict):
    results: list[PlaySessionIngestResult]
    created_count: int
    skipped_count: int


class PlaySessionEntry(TypedDict):
    rom_id: int | None
    save_slot: str | None
    start_time: datetime
    end_time: datetime
    duration_ms: int


def _resolve_device(device_id: str | None, user_id: int) -> str | None:
    if device_id is None:
        return None
    device = db_device_handler.get_device(device_id=device_id, user_id=user_id)
    return device_id if device is not None else None


def _apply_play_to_rom_user(
    rom_user_updates: dict[int, datetime], user_id: int
) -> None:
    for rom_id, latest_end_time in rom_user_updates.items():
        rom_user = db_rom_handler.get_rom_user(rom_id=rom_id, user_id=user_id)
        if not rom_user:
            rom_user = db_rom_handler.add_rom_user(rom_id=rom_id, user_id=user_id)

        current = to_utc(rom_user.last_played) if rom_user.last_played else None
        # Only the newest play advances state. A backfilled or device-synced
        # older session must not resurrect "now playing" or rewind the status.
        if current is not None and latest_end_time <= current:
            continue

        updates: dict[str, Any] = {"last_played": latest_end_time, "now_playing": True}
        # Playing again counts as active: rewind an empty or "finished" status
        # to "incomplete", but leave statuses the user set on purpose
        # (completed_100 / retired / never_playing) untouched.
        if rom_user.status in (None, RomUserStatus.FINISHED):
            updates["status"] = RomUserStatus.INCOMPLETE
        db_rom_handler.update_rom_user(rom_user.id, updates)


def ingest_play_sessions(
    *,
    user_id: int,
    username: str,
    entries: list[PlaySessionEntry],
    device_id: str | None = None,
    max_future_minutes: int = 5,
    perms: ResolvedPermissions | None,
) -> PlaySessionIngestSummary:
    """Core play session ingestion logic shared by the standalone endpoint and sync complete.

    Args:
        perms: The caller's permissions, a rom hidden from them counting as
            unknown; None when its roms were already checked.
    """
    max_future = datetime.now(timezone.utc) + timedelta(minutes=max_future_minutes)
    resolved_device_id = _resolve_device(device_id, user_id)

    # Bulk-resolve all referenced rom IDs in one query
    candidate_rom_ids = {e["rom_id"] for e in entries}
    found_roms = (
        {
            r.id: r
            for r in db_rom_handler.get_roms_by_ids(compact(candidate_rom_ids))
            if perms is None or perms.can_see_rom(r.id, r.platform_id)
        }
        if candidate_rom_ids
        else {}
    )
    valid_rom_ids = set(found_roms)

    # Phase 1: Validate and resolve each entry
    results: list[PlaySessionIngestResult] = []
    valid: list[tuple[int, int | None, PlaySessionEntry]] = []

    for idx, item in enumerate(entries):
        if item["end_time"] > max_future:
            results.append(
                {
                    "index": idx,
                    "status": "error",
                    "detail": "end_time is too far in the future",
                }
            )
            continue

        rom_id = item.get("rom_id")
        resolved_rom_id = rom_id if rom_id in valid_rom_ids else None
        valid.append((idx, resolved_rom_id, item))

    # Phase 2: Batch dedup check
    rom_start_pairs = [
        (rom_id, to_utc(item["start_time"])) for _, rom_id, item in valid
    ]
    existing = db_play_session_handler.find_existing(
        user_id=user_id, device_id=resolved_device_id, rom_start_pairs=rom_start_pairs
    )

    seen: set[tuple[int | None, datetime]] = set()
    to_insert: list[tuple[int, int | None, PlaySession]] = []

    for (idx, resolved_rom_id, item), key in zip(valid, rom_start_pairs, strict=True):
        if key in seen or key in existing:
            results.append({"index": idx, "status": "duplicate"})
            continue
        seen.add(key)

        to_insert.append(
            (
                idx,
                resolved_rom_id,
                PlaySession(
                    user_id=user_id,
                    device_id=resolved_device_id,
                    rom_id=resolved_rom_id,
                    save_slot=item.get("save_slot"),
                    start_time=item["start_time"],
                    end_time=item["end_time"],
                    duration_ms=item["duration_ms"],
                ),
            )
        )

    # Phase 3: Bulk insert
    if to_insert:
        db_play_session_handler.add_sessions([ps for _, _, ps in to_insert])

    rom_user_updates: dict[int, datetime] = {}
    for idx, resolved_rom_id, ps in to_insert:
        results.append({"index": idx, "status": "created", "id": ps.id})
        if resolved_rom_id is not None:
            prev = rom_user_updates.get(resolved_rom_id)
            if prev is None or ps.end_time > prev:
                rom_user_updates[resolved_rom_id] = ps.end_time

    # Phase 4: Side effects
    _apply_play_to_rom_user(rom_user_updates, user_id)

    actor = AuditActor(
        AuditActorKind.USER,
        user_id=user_id,
        name=username,
        device_id=resolved_device_id,
    )
    record_many(
        [
            AuditDraft(
                AuditAction.ROM_PLAY,
                actor,
                AuditTarget.of_rom(found_roms[ps.rom_id]),
                {"duration_ms": ps.duration_ms, "save_slot": ps.save_slot},
                occurred_at=to_utc(ps.start_time),
            )
            for _, _, ps in to_insert
            if ps.rom_id is not None
        ]
    )

    if resolved_device_id is not None:
        db_device_handler.update_last_seen(
            device_id=resolved_device_id, user_id=user_id
        )

    created_count = len(to_insert)
    skipped_count = len(entries) - created_count

    log.info(
        f"Ingested {created_count} play sessions for user {username}"
        f" ({skipped_count} skipped)"
    )

    return {
        "results": results,
        "created_count": created_count,
        "skipped_count": skipped_count,
    }
