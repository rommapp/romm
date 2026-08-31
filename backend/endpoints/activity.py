from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

from decorators.auth import protected_route
from endpoints.responses.activity import ActivityEntrySchema
from handler.activity_handler import ActivityEntry, activity_handler
from handler.auth.constants import Scope
from handler.auth.dependencies import get_permissions
from handler.database import db_device_handler, db_rom_handler
from utils.router import APIRouter

router = APIRouter(
    prefix="/activity",
    tags=["activity"],
)


def _visible_activity(
    request: Request, entries: list[ActivityEntry]
) -> list[ActivityEntrySchema]:
    """Drop sessions whose ROM is hidden from the caller (platform or rom hide)."""
    perms = get_permissions(request)
    if not perms.is_admin and (perms.hidden_platform_ids or perms.hidden_rom_ids):
        rom_ids = [e["rom_id"] for e in entries]
        hidden = db_rom_handler.get_hidden_rom_ids_among(
            rom_ids,
            list(perms.hidden_platform_ids),
            list(perms.hidden_rom_ids),
        )
        entries = [e for e in entries if e["rom_id"] not in hidden]
    return [ActivityEntrySchema(**e) for e in entries]


class DeviceHeartbeatPayload(BaseModel):
    rom_id: int = Field(ge=1)
    device_id: str = Field(min_length=1, max_length=255)


@protected_route(router.get, "", [Scope.ROMS_USER_READ])
async def get_all_activity(request: Request) -> list[ActivityEntrySchema]:
    """Return every currently active play session across all users."""
    entries = await activity_handler.get_all_active()
    return _visible_activity(request, entries)


@protected_route(router.get, "/rom/{rom_id}", [Scope.ROMS_USER_READ])
async def get_rom_activity(request: Request, rom_id: int) -> list[ActivityEntrySchema]:
    """Return all active play sessions for a specific ROM."""
    entries = await activity_handler.get_active_for_rom(rom_id)
    return _visible_activity(request, entries)


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

    entry = await activity_handler.build_entry(
        user_id=request.user.id,
        device_id=device.id,
        rom_id=rom.id,
        preserve_started_at=True,
        device_type=device.client or "unknown",
    )
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ROM {payload.rom_id} not found",
        )

    await activity_handler.publish_active(entry)

    # Update the device last_seen as a side-effect (mirrors play session ingest).
    db_device_handler.update_last_seen(device_id=device.id, user_id=request.user.id)

    return ActivityEntrySchema(**entry)


@protected_route(
    router.delete,
    "/heartbeat",
    [Scope.ROMS_USER_WRITE],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def clear_device_activity(request: Request, device_id: str) -> None:
    """Immediately clear an active session for a device (e.g. on graceful exit)."""
    await activity_handler.publish_clear(request.user.id, device_id)
    return None
