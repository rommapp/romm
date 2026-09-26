import asyncio
from collections import Counter
from datetime import datetime

from fastapi import BackgroundTasks, HTTPException, Request, status
from pydantic import Field, model_validator

from config import TASK_TIMEOUT
from decorators.auth import protected_route
from endpoints.responses.base import BaseModel
from endpoints.responses.play_session import (
    PlaySessionIngestResponse,
    PlaySessionIngestResult,
)
from endpoints.responses.sync import (
    SyncCompleteResponse,
    SyncNegotiateResponse,
    SyncOperationSchema,
    SyncSessionSchema,
)
from endpoints.sockets.sync import emit_sync_conflict
from handler.auth.constants import Scope
from handler.auth.dependencies import get_permissions
from handler.database import (
    db_deleted_asset_handler,
    db_device_handler,
    db_device_save_sync_handler,
    db_save_handler,
    db_sync_session_handler,
)
from handler.play_session_handler import ingest_play_sessions
from handler.redis_handler import high_prio_queue
from handler.sync.comparison import compare_missing_server_save, compare_save_state
from logger.logger import log
from models.assets import Save
from models.deleted_asset import DeletedAsset
from models.device import SyncMode
from models.sync_session import SyncSessionStatus
from utils.datetime import to_utc
from utils.router import APIRouter
from utils.validation import MAX_ROM_IDS_PER_QUERY, RomIdScope

from .retroarch import router as retroarch_router

router = APIRouter(
    prefix="/sync",
    tags=["sync"],
)
router.include_router(retroarch_router)

# A hung broker must not pin the background task forever.
CONFLICT_NOTIFY_TIMEOUT_S = 2.0


class ClientSaveState(BaseModel):
    rom_id: int = Field(description="ID of the ROM this save belongs to.")
    file_name: str = Field(description="Name of the save file on the client.")
    slot: str | None = Field(
        default=None,
        description=(
            "Save slot name. Saves are paired between client and server on "
            "(rom_id, slot), so provide a stable slot name (e.g. 'autosave') to "
            "keep a save in sync across negotiations. A null slot is treated as "
            "an archival, manual-upload save: it is never paired with slotted "
            "server saves, so a null-slot client save always negotiates as an "
            "'upload' even when an identical file already exists on the server "
            "under a slot."
        ),
    )
    emulator: str | None = Field(
        default=None, description="Emulator that produced the save, if known."
    )
    content_hash: str | None = Field(
        default=None,
        description="Hash of the save contents, used to detect identical saves.",
    )
    updated_at: datetime = Field(
        description="Last-modified timestamp of the save on the client."
    )
    file_size_bytes: int = Field(description="Size of the save file in bytes.")


class SyncNegotiatePayload(BaseModel):
    device_id: str | None = Field(
        default=None,
        description=(
            "ID of the syncing device. Optional when the request uses a "
            "device-bound client token, in which case the device is inferred "
            "from the token."
        ),
    )
    saves: list[ClientSaveState] = Field(
        description="Current save state on the client."
    )
    rom_ids: RomIdScope = Field(
        default=None,
        description=(
            "IDs of the ROMs installed on the device. When provided, downloads "
            "are offered only for these ROMs (plus any ROM the client sent a "
            "save for) instead of the user's whole save library. This is a "
            "read-only scope: omitting a ROM never deletes or unlinks its "
            f"saves. At most {MAX_ROM_IDS_PER_QUERY} IDs per request."
        ),
    )


class SyncPlaySessionEntry(BaseModel):
    rom_id: int | None = None
    save_slot: str | None = None
    start_time: datetime
    end_time: datetime
    duration_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_times(self) -> "SyncPlaySessionEntry":
        self.start_time = self.start_time.replace(microsecond=0)
        self.end_time = self.end_time.replace(microsecond=0)
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class SyncCompletePayload(BaseModel):
    operations_completed: int = 0
    operations_failed: int = 0
    play_sessions: list[SyncPlaySessionEntry] | None = None


async def _notify_conflicts(
    user_id: int,
    device_id: str,
    session_id: int,
    conflict_ops: list[SyncOperationSchema],
    rom_names: dict[int, str],
) -> None:
    """Emit one sync:conflict event per operation, within one deadline."""
    try:
        async with asyncio.timeout(CONFLICT_NOTIFY_TIMEOUT_S):
            for op in conflict_ops:
                await emit_sync_conflict(
                    user_id=user_id,
                    device_id=device_id,
                    session_id=session_id,
                    file_name=op.file_name,
                    rom_id=op.rom_id,
                    rom_name=rom_names[op.rom_id],
                    reason=op.reason,
                )
    except TimeoutError:
        log.warning(
            f"Gave up on {len(conflict_ops)} sync:conflict events "
            f"after {CONFLICT_NOTIFY_TIMEOUT_S}s"
        )


@protected_route(router.post, "/negotiate", [Scope.ASSETS_READ, Scope.DEVICES_READ])
def negotiate_sync(
    request: Request,
    payload: SyncNegotiatePayload,
    background_tasks: BackgroundTasks,
) -> SyncNegotiateResponse:
    """Negotiate sync operations between a client device and the server.

    The client sends its current save state, and the server returns a list of
    operations (upload, download, conflict, delete, no_op) to bring both sides
    in sync.

    A client that only holds part of the library can send `rom_ids` to scope the
    negotiation to the ROMs installed on the device, which keeps the response
    from listing downloads for ROMs it cannot play. The scope is read-only: a
    ROM left out is simply outside this negotiation, never a deletion signal.

    Saves are paired on (rom_id, slot). Clients that want a save to stay in sync
    should send a stable, non-null slot name (e.g. "autosave"). Null-slot saves
    are treated as archival, manual uploads: they are excluded from pairing, so a
    null-slot client save always negotiates as an "upload" even when an identical
    file (same content_hash) already exists on the server under a slot. This is
    intentional, since saves can be cloned across slots and null slots overlap
    with manual uploads.
    """
    device_id: str | None = payload.device_id or getattr(
        request.state, "device_id", None
    )
    if not device_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "device_id is required (either in the request payload or "
                "implicit via a device-bound client token)"
            ),
        )

    device = db_device_handler.get_device(device_id=device_id, user_id=request.user.id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found",
        )

    if not device.sync_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sync is disabled for this device",
        )

    # A session belongs to the launch that negotiated it, not to the device,
    # which can have two games open at once. One nobody closes is left to the
    # scheduled cleanup rather than to the next negotiation.
    sync_session = db_sync_session_handler.create_session(
        device_id=device.id, user_id=request.user.id
    )

    operations: list[SyncOperationSchema] = []

    # Widen an explicit ROM scope with the ROMs the client sent saves for, so a
    # client save is never misread as an upload just because its ROM was omitted.
    rom_id_scope = (
        payload.rom_ids + [s.rom_id for s in payload.saves]
        if payload.rom_ids is not None
        else None
    )

    # Pair on (rom_id, slot), keeping the newest row per slot: slot uploads are datetime-tagged (spec) so tagged filenames never equal the client's untagged name, and a slot accrues many rows over time. Null-slot rows stay archival-only.
    server_saves = db_save_handler.get_saves(
        user_id=request.user.id, slot_not_null=True, rom_ids=rom_id_scope
    )
    server_save_map: dict[tuple[int, str | None], Save] = {}
    for save in server_saves:
        key = (save.rom_id, save.slot)
        current = server_save_map.get(key)
        if current is None or to_utc(save.updated_at) > to_utc(current.updated_at):
            server_save_map[key] = save

    # Read only when a slot has no row left, so a slot refilled since keeps
    # its record harmlessly.
    emptied_rom_ids = {
        s.rom_id
        for s in payload.saves
        if s.slot and (s.rom_id, s.slot) not in server_save_map
    }
    deleted_map: dict[tuple[int, str | None], DeletedAsset] = {
        (record.rom_id, record.slot): record
        for record in db_deleted_asset_handler.get_deletions(
            user_id=request.user.id, rom_ids=emptied_rom_ids
        )
    }

    # Only the newest row per slot is ever looked up, so superseded rows stay out.
    current_save_ids = [s.id for s in server_save_map.values()]
    device_syncs = db_device_save_sync_handler.get_syncs_for_device_and_saves(
        device_id=device.id, save_ids=current_save_ids
    )
    sync_by_save_id = {s.save_id: s for s in device_syncs}

    # Track which server saves were referenced by the client
    matched_server_save_ids: set[int] = set()

    # Process each client save
    for client_save in payload.saves:
        key = (client_save.rom_id, client_save.slot)
        server_save = server_save_map.get(key)

        if server_save is None:
            # Without this the client offers the save back and the deletion
            # undoes itself.
            deletion = deleted_map.get(key)
            result = compare_missing_server_save(
                client_save.content_hash, deletion.content_hashes if deletion else ()
            )
            operations.append(
                SyncOperationSchema(
                    action=result.action,
                    rom_id=client_save.rom_id,
                    save_id=None,
                    file_name=client_save.file_name,
                    slot=client_save.slot,
                    emulator=client_save.emulator,
                    reason=result.reason,
                )
            )
            continue

        matched_server_save_ids.add(server_save.id)
        device_sync = sync_by_save_id.get(server_save.id)

        # Skip untracked saves
        if device_sync and device_sync.is_untracked:
            operations.append(
                SyncOperationSchema(
                    action="no_op",
                    rom_id=server_save.rom_id,
                    save_id=server_save.id,
                    file_name=server_save.file_name,
                    slot=server_save.slot,
                    emulator=server_save.emulator,
                    reason="Save is untracked on this device",
                )
            )
            continue

        result = compare_save_state(
            client_hash=client_save.content_hash,
            client_updated_at=client_save.updated_at,
            server_hash=server_save.content_hash,
            server_updated_at=server_save.updated_at,
            device_last_synced_at=device_sync.last_synced_at if device_sync else None,
            device_last_sync_hash=device_sync.last_sync_hash if device_sync else None,
            device_last_sync_server_hash=(
                device_sync.last_sync_server_hash if device_sync else None
            ),
        )
        if (
            result.action == "no_op"
            and client_save.content_hash == server_save.content_hash
        ):
            db_device_save_sync_handler.record_identical_content(
                device.id,
                server_save.id,
                server_save.content_hash,
                synced_at=server_save.updated_at,
            )

        operations.append(
            SyncOperationSchema(
                action=result.action,
                rom_id=server_save.rom_id,
                save_id=server_save.id,
                file_name=server_save.file_name,
                slot=server_save.slot,
                emulator=server_save.emulator,
                reason=result.reason,
                server_updated_at=server_save.updated_at,
                server_content_hash=server_save.content_hash,
            )
        )

    # Check for current saves the client didn't mention (superseded older rows per slot are history, not downloads)
    for save in server_save_map.values():
        if save.id in matched_server_save_ids:
            continue

        device_sync = sync_by_save_id.get(save.id)

        # Skip untracked saves
        if device_sync and device_sync.is_untracked:
            continue

        # If device has synced this save before and the save hasn't changed,
        # the client intentionally deleted it - treat as no_op
        if device_sync:
            synced_ts = to_utc(device_sync.last_synced_at)
            save_ts = to_utc(save.updated_at)
            if save_ts <= synced_ts:
                # Save hasn't changed since device last synced - client deleted it
                continue

            # Save changed after device last synced - device should download
            operations.append(
                SyncOperationSchema(
                    action="download",
                    rom_id=save.rom_id,
                    save_id=save.id,
                    file_name=save.file_name,
                    slot=save.slot,
                    emulator=save.emulator,
                    reason="Server save updated since last sync, not present on client",
                    server_updated_at=save.updated_at,
                    server_content_hash=save.content_hash,
                )
            )
        else:
            # Device has never synced this save - download it
            operations.append(
                SyncOperationSchema(
                    action="download",
                    rom_id=save.rom_id,
                    save_id=save.id,
                    file_name=save.file_name,
                    slot=save.slot,
                    emulator=save.emulator,
                    reason="Save exists on server but not on client",
                    server_updated_at=save.updated_at,
                    server_content_hash=save.content_hash,
                )
            )

    # Update session with operation counts
    counts = Counter(op.action for op in operations)

    db_sync_session_handler.update_session(
        session_id=sync_session.id,
        data={
            "status": SyncSessionStatus.IN_PROGRESS,
            "operations_planned": len(operations) - counts["no_op"],
        },
    )

    # Update device last_seen
    db_device_handler.update_last_seen(device_id=device.id, user_id=request.user.id)

    log.info(
        f"Sync negotiation for device {device.id}: "
        f"{counts['upload']} uploads, {counts['download']} downloads, "
        f"{counts['conflict']} conflicts, {counts['delete']} deletions, "
        f"{counts['no_op']} no-ops"
    )

    # Sent after the response on the app's loop, so a slow broker never holds
    # up the client and the shared socket manager stays on one loop.
    conflict_ops = [op for op in operations if op.action == "conflict"]
    if conflict_ops:
        background_tasks.add_task(
            _notify_conflicts,
            user_id=request.user.id,
            device_id=device.id,
            session_id=sync_session.id,
            conflict_ops=conflict_ops,
            rom_names={
                save.rom_id: save.rom.name or save.rom.fs_name
                for save in server_save_map.values()
            },
        )

    return SyncNegotiateResponse(
        session_id=sync_session.id,
        operations=operations,
        total_upload=counts["upload"],
        total_download=counts["download"],
        total_conflict=counts["conflict"],
        total_no_op=counts["no_op"],
        total_delete=counts["delete"],
    )


@protected_route(router.post, "/sessions/{session_id}/complete", [Scope.DEVICES_WRITE])
def complete_sync_session(
    request: Request,
    session_id: int,
    payload: SyncCompletePayload,
) -> SyncCompleteResponse:
    """Mark a sync session as completed, optionally ingesting play sessions."""
    sync_session = db_sync_session_handler.get_session(
        session_id=session_id, user_id=request.user.id
    )
    if not sync_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sync session with ID {session_id} not found",
        )

    # A session the cleanup expired can still be completed: its counts and the
    # play sessions the client carries are worth more than the guess that
    # nobody would ever report them. One closed on purpose is refused.
    completed = db_sync_session_handler.complete_session(
        session_id=session_id,
        operations_completed=payload.operations_completed,
        operations_failed=payload.operations_failed,
    )
    if completed is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session is already {sync_session.status}",
        )

    log.info(
        f"Sync session {session_id} completed: "
        f"{payload.operations_completed} succeeded, {payload.operations_failed} failed"
    )

    play_session_ingest = None
    if payload.play_sessions:
        summary = ingest_play_sessions(
            user_id=request.user.id,
            username=request.user.username,
            perms=get_permissions(request),
            entries=[
                {
                    "rom_id": s.rom_id,
                    "save_slot": s.save_slot,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "duration_ms": s.duration_ms,
                }
                for s in payload.play_sessions
            ],
            device_id=sync_session.device_id,
        )
        play_session_ingest = PlaySessionIngestResponse(
            results=[
                PlaySessionIngestResult(
                    index=r["index"],
                    status=r["status"],
                    id=r.get("id"),
                    detail=r.get("detail"),
                )
                for r in summary["results"]
            ],
            created_count=summary["created_count"],
            skipped_count=summary["skipped_count"],
        )

    return SyncCompleteResponse(
        session=SyncSessionSchema.model_validate(completed),
        play_session_ingest=play_session_ingest,
    )


@protected_route(router.get, "/sessions", [Scope.DEVICES_READ])
def get_sync_sessions(
    request: Request,
    device_id: str | None = None,
    limit: int = 50,
) -> list[SyncSessionSchema]:
    """List sync sessions for the current user."""
    sessions = db_sync_session_handler.get_sessions(
        user_id=request.user.id,
        device_id=device_id,
        limit=limit,
    )
    return [SyncSessionSchema.model_validate(s) for s in sessions]


@protected_route(router.get, "/sessions/{session_id}", [Scope.DEVICES_READ])
def get_sync_session(
    request: Request,
    session_id: int,
) -> SyncSessionSchema:
    """Get a specific sync session."""
    sync_session = db_sync_session_handler.get_session(
        session_id=session_id, user_id=request.user.id
    )
    if not sync_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sync session with ID {session_id} not found",
        )

    return SyncSessionSchema.model_validate(sync_session)


# --- Push-Pull Mode Endpoints ---


@protected_route(router.post, "/devices/{device_id}/push-pull", [Scope.DEVICES_WRITE])
def trigger_push_pull(
    request: Request,
    device_id: str,
) -> SyncSessionSchema:
    """Manually trigger a push-pull sync for a specific device."""
    device = db_device_handler.get_device(device_id=device_id, user_id=request.user.id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found",
        )

    if device.sync_mode != SyncMode.PUSH_PULL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device is not in push_pull sync mode",
        )

    if not device.sync_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sync is disabled for this device",
        )

    # Create a session and enqueue the job
    sync_session = db_sync_session_handler.create_session(
        device_id=device.id, user_id=request.user.id
    )

    high_prio_queue.enqueue(
        "tasks.sync_push_pull_task.run_push_pull_sync",
        device_id=device.id,
        session_id=sync_session.id,
        force=True,
        job_timeout=TASK_TIMEOUT,
        meta={
            "task_key": "sync_push_pull",
            "task_name": "Push-Pull Sync",
            "task_type": "sync",
        },
    )

    log.info(f"Enqueued push-pull sync for device {device.id}")
    return SyncSessionSchema.model_validate(sync_session)
