from datetime import datetime, timedelta, timezone
from typing import Literal, NotRequired, TypedDict

from pydash import compact

from handler.database import db_device_handler, db_play_session_handler, db_rom_handler
from logger.logger import log
from models.play_session import PlaySession
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


def _update_rom_user_last_played(
    rom_user_updates: dict[int, datetime], user_id: int
) -> None:
    for rom_id, latest_end_time in rom_user_updates.items():
        rom_user = db_rom_handler.get_rom_user(rom_id=rom_id, user_id=user_id)
        if not rom_user:
            rom_user = db_rom_handler.add_rom_user(rom_id=rom_id, user_id=user_id)

        current = to_utc(rom_user.last_played) if rom_user.last_played else None
        if current is None or latest_end_time > current:
            db_rom_handler.update_rom_user(
                rom_user.id, {"last_played": latest_end_time}
            )


def ingest_play_sessions(
    *,
    user_id: int,
    username: str,
    entries: list[PlaySessionEntry],
    device_id: str | None = None,
    sync_session_id: int | None = None,
    max_future_minutes: int = 5,
) -> PlaySessionIngestSummary:
    """Core play session ingestion logic shared by the standalone endpoint and sync complete."""
    max_future = datetime.now(timezone.utc) + timedelta(minutes=max_future_minutes)
    resolved_device_id = _resolve_device(device_id, user_id)

    # Bulk-resolve all referenced rom IDs in one query
    candidate_rom_ids = {e["rom_id"] for e in entries}
    valid_rom_ids: set[int] = set()
    if candidate_rom_ids:
        found_roms = db_rom_handler.get_roms_by_ids(compact(candidate_rom_ids))
        valid_rom_ids = {r.id for r in found_roms}

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
                    sync_session_id=sync_session_id,
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
    _update_rom_user_last_played(rom_user_updates, user_id)

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
