from typing import Annotated

from fastapi import HTTPException
from fastapi import Path as PathVar
from fastapi import Query, Request, status

from decorators.auth import protected_route
from endpoints.responses.shortcut import (
    ShortcutAckStatus,
    ShortcutCreatePayload,
    ShortcutSchema,
    SteamArtworkSchema,
)
from endpoints.sockets.shortcuts import emit_shortcuts_changed
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from handler.auth.constants import Scope
from handler.auth.dependencies import assert_rom_visible
from handler.database import db_device_handler, db_rom_handler, db_shortcut_handler
from handler.metadata.sgdb_handler import sgdb_handler
from logger.logger import log
from models.shortcut import ShortcutStatus
from utils.router import APIRouter

router = APIRouter(
    prefix="/shortcuts",
    tags=["shortcuts"],
)

# The literal a launcher client passes to mean "the device my token is bound to".
DEVICE_ME = "me"


def _resolve_device_id(request: Request, device_id: str | None) -> str | None:
    if device_id != DEVICE_ME:
        return device_id
    bound = getattr(request.state, "device_id", None)
    if not bound:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="device_id=me requires a client token bound to a device",
        )
    return bound


def _parse_statuses(raw: str | None) -> list[ShortcutStatus] | None:
    if not raw:
        return None
    try:
        return [ShortcutStatus(s.strip()) for s in raw.split(",") if s.strip()]
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown shortcut status in {raw!r}",
        ) from exc


@protected_route(router.get, "", [Scope.ROMS_USER_READ])
def get_shortcuts(
    request: Request,
    rom_id: Annotated[int | None, Query(description="Filter by rom id")] = None,
    device_id: Annotated[
        str | None,
        Query(description="Filter by device id; 'me' for the token's own device"),
    ] = None,
    status_filter: Annotated[
        str | None,
        Query(alias="status", description="Comma-separated shortcut statuses"),
    ] = None,
) -> list[ShortcutSchema]:
    """List the current user's shortcuts, filtered for a game or a device queue."""
    shortcuts = db_shortcut_handler.get_shortcuts(
        user_id=request.user.id,
        rom_id=rom_id,
        device_id=_resolve_device_id(request, device_id),
        statuses=_parse_statuses(status_filter),
    )
    return [ShortcutSchema.model_validate(s) for s in shortcuts]


@protected_route(router.put, "", [Scope.ROMS_USER_WRITE])
async def upsert_shortcut(
    request: Request, payload: ShortcutCreatePayload
) -> ShortcutSchema:
    """Ask a paired device to add a game to its launcher."""
    device = db_device_handler.get_device(
        device_id=payload.device_id, user_id=request.user.id
    )
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {payload.device_id} not found",
        )
    rom = db_rom_handler.get_rom(payload.rom_id)
    if not rom:
        raise RomNotFoundInDatabaseException(payload.rom_id)
    assert_rom_visible(request, rom)

    shortcut = db_shortcut_handler.upsert_pending_add(
        user_id=request.user.id,
        device_id=device.id,
        rom_id=rom.id,
        launch_mode=payload.launch_mode,
    )
    await emit_shortcuts_changed(device.id, request.user.id)
    log.info(f"Queued rom {rom.id} for launcher on device {device.id}")
    return ShortcutSchema.model_validate(shortcut)


@protected_route(router.delete, "/{shortcut_id}", [Scope.ROMS_USER_WRITE])
async def remove_shortcut(request: Request, shortcut_id: int) -> ShortcutSchema:
    """Ask the device to remove the game. The row is deleted once the device
    confirms; until then it reads as pending_remove."""
    shortcut = db_shortcut_handler.get_shortcut(
        shortcut_id=shortcut_id, user_id=request.user.id
    )
    if not shortcut:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Shortcut not found"
        )
    # Nothing has reached the device yet, so there is nothing to undo there.
    if shortcut.status == ShortcutStatus.PENDING_ADD:
        db_shortcut_handler.delete_shortcut(shortcut_id=shortcut.id)
        await emit_shortcuts_changed(shortcut.device_id, request.user.id)
        return ShortcutSchema.model_validate(shortcut)

    updated = db_shortcut_handler.mark_pending_remove(shortcut_id=shortcut.id)
    await emit_shortcuts_changed(shortcut.device_id, request.user.id)
    return ShortcutSchema.model_validate(updated)


@protected_route(router.post, "/{shortcut_id}/ack", [Scope.DEVICES_WRITE])
async def ack_shortcut(
    request: Request, shortcut_id: int, payload: ShortcutAckStatus
) -> ShortcutSchema | None:
    """Launcher client reports the outcome of a queued shortcut."""
    shortcut = db_shortcut_handler.get_shortcut(
        shortcut_id=shortcut_id, user_id=request.user.id
    )
    if not shortcut:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Shortcut not found"
        )
    # Acknowledgements are device-originated, so an unbound caller (a browser
    # session, or a client token with devices.write and no device) has nothing
    # to report and is refused alongside a token bound elsewhere.
    if getattr(request.state, "device_id", None) != shortcut.device_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acknowledgements must come from the device that owns the shortcut",
        )

    # A confirmed removal deletes the row rather than storing a status.
    if payload.status == "removed":
        db_shortcut_handler.delete_shortcut(shortcut_id=shortcut.id)
        await emit_shortcuts_changed(shortcut.device_id, request.user.id)
        return None

    updated = db_shortcut_handler.ack(
        shortcut_id=shortcut.id,
        status=ShortcutStatus(payload.status),
        steam_app_id=payload.steam_app_id,
        error=payload.error,
    )
    await emit_shortcuts_changed(shortcut.device_id, request.user.id)
    return ShortcutSchema.model_validate(updated)


@protected_route(router.get, "/artwork/{rom_id}", [Scope.ROMS_READ])
async def get_steam_artwork(
    request: Request,
    rom_id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
) -> SteamArtworkSchema:
    """Steam library art for a rom, so a launcher client needs no SteamGridDB key."""
    rom = db_rom_handler.get_rom(rom_id)
    if not rom:
        raise RomNotFoundInDatabaseException(rom_id)
    assert_rom_visible(request, rom)

    if not rom.sgdb_id:
        return SteamArtworkSchema()

    artwork = await sgdb_handler.get_steam_artwork(rom.sgdb_id)
    return SteamArtworkSchema(
        url_hero=artwork["url_hero"], url_logo=artwork["url_logo"]
    )
