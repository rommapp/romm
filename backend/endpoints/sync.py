from datetime import datetime

from fastapi import HTTPException, Request, status

from config import TASK_TIMEOUT
from decorators.auth import protected_route
from endpoints.responses.base import BaseModel
from endpoints.responses.sync import (
    SyncNegotiateResponse,
    SyncOperationSchema,
    SyncSessionSchema,
)
from handler.auth.constants import Scope
from handler.database import (
    db_device_handler,
    db_device_save_sync_handler,
    db_save_handler,
    db_sync_session_handler,
)
from handler.redis_handler import high_prio_queue
from handler.sync.comparison import compare_save_state
from logger.logger import log
from models.assets import Save
from models.device import SyncMode
from models.sync_session import SyncSessionStatus
from utils.datetime import to_utc
from utils.router import APIRouter

router = APIRouter(
    prefix="/sync",
    tags=["sync"],
)


class ClientSaveState(BaseModel):
    rom_id: int
    file_name: str
    slot: str | None = None
    emulator: str | None = None
    content_hash: str | None = None
    updated_at: datetime
    file_size_bytes: int


class SyncNegotiatePayload(BaseModel):
    device_id: str
    saves: list[ClientSaveState]


class SyncCompletePayload(BaseModel):
    operations_completed: int = 0
    operations_failed: int = 0


@protected_route(router.post, "/negotiate", [Scope.ASSETS_READ, Scope.DEVICES_READ])
def negotiate_sync(
    request: Request,
    payload: SyncNegotiatePayload,
) -> SyncNegotiateResponse:
    """Negotiate sync operations between a client device and the server.

    The client sends its current save state, and the server returns a list of
    operations (upload, download, conflict, no_op) to bring both sides in sync.
    """
    device = db_device_handler.get_device(
        device_id=payload.device_id, user_id=request.user.id
    )
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {payload.device_id} not found",
        )

    if not device.sync_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sync is disabled for this device",
        )

    # Cancel any existing active sessions for this device
    cancelled = db_sync_session_handler.cancel_active_sessions(
        device_id=device.id, user_id=request.user.id
    )
    if cancelled:
        log.info(f"Cancelled {cancelled} active sync session(s) for device {device.id}")

    # Create a new sync session
    sync_session = db_sync_session_handler.create_session(
        device_id=device.id, user_id=request.user.id
    )

    operations: list[SyncOperationSchema] = []

    # Build a set of server saves for this user, keyed by (rom_id, file_name)
    # We'll also track which server saves were mentioned by the client
    server_saves = db_save_handler.get_saves(user_id=request.user.id)
    server_save_map: dict[tuple[int, str], Save] = {}
    for save in server_saves:
        server_save_map[(save.rom_id, save.file_name)] = save

    # Get all sync records for this device
    all_save_ids = [s.id for s in server_saves]
    device_syncs = db_device_save_sync_handler.get_syncs_for_device_and_saves(
        device_id=device.id, save_ids=all_save_ids
    )
    sync_by_save_id = {s.save_id: s for s in device_syncs}

    # Track which server saves were referenced by the client
    matched_server_save_ids: set[int] = set()

    # Process each client save
    for client_save in payload.saves:
        key = (client_save.rom_id, client_save.file_name)
        server_save = server_save_map.get(key)

        if server_save is None:
            # Client has a save the server doesn't -> upload
            operations.append(
                SyncOperationSchema(
                    action="upload",
                    rom_id=client_save.rom_id,
                    save_id=None,
                    file_name=client_save.file_name,
                    slot=client_save.slot,
                    emulator=client_save.emulator,
                    reason="Save exists on client but not on server",
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

    # Check for server saves the client didn't mention
    for save in server_saves:
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
    total_upload = sum(1 for op in operations if op.action == "upload")
    total_download = sum(1 for op in operations if op.action == "download")
    total_conflict = sum(1 for op in operations if op.action == "conflict")
    total_no_op = sum(1 for op in operations if op.action == "no_op")

    db_sync_session_handler.update_session(
        session_id=sync_session.id,
        data={
            "status": SyncSessionStatus.IN_PROGRESS,
            "operations_planned": total_upload + total_download + total_conflict,
        },
    )

    # Update device last_seen
    db_device_handler.update_last_seen(device_id=device.id, user_id=request.user.id)

    log.info(
        f"Sync negotiation for device {device.id}: "
        f"{total_upload} uploads, {total_download} downloads, "
        f"{total_conflict} conflicts, {total_no_op} no-ops"
    )

    return SyncNegotiateResponse(
        session_id=sync_session.id,
        operations=operations,
        total_upload=total_upload,
        total_download=total_download,
        total_conflict=total_conflict,
        total_no_op=total_no_op,
    )


@protected_route(router.post, "/sessions/{session_id}/complete", [Scope.DEVICES_WRITE])
def complete_sync_session(
    request: Request,
    session_id: int,
    payload: SyncCompletePayload,
) -> SyncSessionSchema:
    """Mark a sync session as completed."""
    sync_session = db_sync_session_handler.get_session(
        session_id=session_id, user_id=request.user.id
    )
    if not sync_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sync session with ID {session_id} not found",
        )

    if sync_session.status not in (
        SyncSessionStatus.PENDING,
        SyncSessionStatus.IN_PROGRESS,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session is already {sync_session.status}",
        )

    completed = db_sync_session_handler.complete_session(
        session_id=session_id,
        operations_completed=payload.operations_completed,
        operations_failed=payload.operations_failed,
    )

    log.info(
        f"Sync session {session_id} completed: "
        f"{payload.operations_completed} succeeded, {payload.operations_failed} failed"
    )

    return SyncSessionSchema.model_validate(completed)


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
            "task_name": "Push-Pull Sync",
            "task_type": "sync",
        },
    )

    log.info(f"Enqueued push-pull sync for device {device.id}")
    return SyncSessionSchema.model_validate(sync_session)
