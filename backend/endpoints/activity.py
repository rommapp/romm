from datetime import datetime, timezone

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

from decorators.auth import protected_route
from endpoints.responses.activity import ActivityClearSchema, ActivityEntrySchema
from handler.activity_handler import ActivityEntry, activity_handler
from handler.auth.constants import Scope
from handler.database import db_device_handler, db_rom_handler
from handler.socket_handler import socket_handler
from logger.logger import log
from utils.router import APIRouter

router = APIRouter(
    prefix="/activity",
    tags=["activity"],
)


class DeviceHeartbeatPayload(BaseModel):
    rom_id: int = Field(ge=1)
    device_id: str = Field(min_length=1, max_length=255)


@protected_route(router.get, "", [Scope.ROMS_USER_READ])
async def get_all_activity(request: Request) -> list[ActivityEntrySchema]:
    """Return every currently active play session across all users."""
    entries = await activity_handler.get_all_active()
    return [ActivityEntrySchema(**e) for e in entries]


@protected_route(router.get, "/rom/{rom_id}", [Scope.ROMS_USER_READ])
async def get_rom_activity(request: Request, rom_id: int) -> list[ActivityEntrySchema]:
    """Return all active play sessions for a specific ROM."""
    entries = await activity_handler.get_active_for_rom(rom_id)
    return [ActivityEntrySchema(**e) for e in entries]


@protected_route(router.post, "/heartbeat", [Scope.ROMS_USER_WRITE])
async def device_heartbeat(
    request: Request, payload: DeviceHeartbeatPayload
) -> ActivityEntrySchema:
    """Heartbeat endpoint for external devices (muOS, Android, etc.).

    Called periodically by devices while the user is playing a game. Writes
    activity state to Redis and broadcasts an ``activity:update`` event over
    the main Socket.IO namespace.
    """
    rom = db_rom_handler.get_rom(payload.rom_id)
    if rom is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ROM {payload.rom_id} not found",
        )

    device = db_device_handler.get_device(
        device_id=payload.device_id, user_id=request.user.id
    )
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {payload.device_id} not found for this user",
        )

    # Preserve the started_at from the existing entry if we are refreshing.
    existing = await activity_handler.get_active(request.user.id, device.id)
    started_at = (
        existing["started_at"] if existing else datetime.now(timezone.utc).isoformat()
    )

    platform = rom.platform
    entry = ActivityEntry(
        user_id=request.user.id,
        username=request.user.username,
        avatar_path=request.user.avatar_path or "",
        rom_id=rom.id,
        rom_name=rom.name or rom.fs_name,
        rom_cover_path=rom.path_cover_s or "",
        platform_slug=platform.slug if platform else "",
        platform_name=(platform.custom_name or platform.name) if platform else "",
        device_id=device.id,
        device_type=device.client or "unknown",
        started_at=started_at,
    )

    await activity_handler.set_active(entry)

    # Update the device last_seen as a side-effect (mirrors play session ingest).
    db_device_handler.update_last_seen(device_id=device.id, user_id=request.user.id)

    # Broadcast to all connected sockets. The REST app shares this process with
    # the Socket.IO server, so emit through the already-initialised, Redis-backed
    # server (it fans out across workers) rather than opening a manager per call.
    try:
        await socket_handler.socket_server.emit("activity:update", dict(entry))
    except Exception as e:  # noqa: BLE001
        log.warning(
            f"Failed to broadcast activity:update for user {request.user.id}: {e}"
        )

    return ActivityEntrySchema(**entry)


@protected_route(
    router.delete,
    "/heartbeat",
    [Scope.ROMS_USER_WRITE],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def clear_device_activity(request: Request, device_id: str) -> None:
    """Immediately clear an active session for a device (e.g. on graceful exit)."""
    rom_id = await activity_handler.clear_active(request.user.id, device_id)
    if rom_id is None:
        return None

    try:
        await socket_handler.socket_server.emit(
            "activity:clear",
            ActivityClearSchema(
                user_id=request.user.id,
                device_id=device_id,
                rom_id=rom_id,
            ).model_dump(),
        )
    except Exception as e:  # noqa: BLE001
        log.warning(
            f"Failed to broadcast activity:clear for user {request.user.id}: {e}"
        )
    return None
