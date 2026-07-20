import os
import re
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Body, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse

from decorators.auth import protected_route
from endpoints.responses.assets import SaveSchema, SaveSummarySchema, SlotSummarySchema
from endpoints.responses.device import DeviceSyncSchema
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from handler.auth.constants import Scope
from handler.database import (
    db_device_handler,
    db_device_save_sync_handler,
    db_rom_handler,
    db_save_handler,
    db_screenshot_handler,
    db_sync_session_handler,
)
from handler.filesystem import fs_asset_handler
from handler.scan_handler import scan_save, scan_screenshot
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.assets import Save
from models.device import Device
from models.device_save_sync import DeviceSaveSync
from utils.datetime import to_utc
from utils.filesystem import sanitize_filename
from utils.router import APIRouter


def _build_save_schema(
    save: Save,
    syncs: Sequence[tuple[DeviceSaveSync, str | None]] = (),
    device: Device | None = None,
) -> SaveSchema:
    """Attach one ``DeviceSyncSchema`` per device that has synced this save.

    ``syncs`` is the full list of sync rows (paired with device name) for this
    save across every device, so clients can attribute the save to its creator.
    ``device`` is the caller's device, when supplied: its entry is emitted first
    for stable ordering and old-client compatibility, and a placeholder entry is
    synthesized when the caller has not yet synced this save.
    """
    save_schema = SaveSchema.model_validate(save)

    save_updated = to_utc(save.updated_at)
    caller_present = False
    entries: list[DeviceSyncSchema] = []
    for sync, device_name in syncs:
        if device and sync.device_id == device.id:
            caller_present = True
        entries.append(
            DeviceSyncSchema(
                device_id=sync.device_id,
                device_name=device_name,
                last_synced_at=sync.last_synced_at,
                is_untracked=sync.is_untracked,
                is_current=to_utc(sync.last_synced_at) >= save_updated,
            )
        )

    if device and not caller_present:
        entries.append(
            DeviceSyncSchema(
                device_id=device.id,
                device_name=device.name,
                last_synced_at=save.updated_at,
                is_untracked=False,
                is_current=False,
            )
        )

    if device:
        entries.sort(key=lambda entry: entry.device_id != device.id)

    save_schema.device_syncs = entries
    return save_schema


def _syncs_for_save(
    save_id: int, device: Device | None
) -> list[tuple[DeviceSaveSync, str | None]]:
    """Fetch every device sync for a single save when a device is in context.

    Device attribution is only meaningful to a device-scoped caller, so callers
    without a device get an empty list and no query is issued.
    """
    if not device:
        return []
    return db_device_save_sync_handler.get_syncs_for_saves([save_id]).get(save_id, [])


DATETIME_TAG_PATTERN = re.compile(r" \[\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\]")


def _apply_datetime_tag(filename: str) -> str:
    name, ext = os.path.splitext(filename)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")

    if DATETIME_TAG_PATTERN.search(name):
        name = DATETIME_TAG_PATTERN.sub("", name)

    return f"{name} [{timestamp}]{ext}"


def _resolve_device(
    device_id: str | None,
    user_id: int,
    scopes: set[str] | None = None,
    required_scope: Scope | None = None,
) -> Device | None:
    if not device_id:
        return None

    if required_scope and scopes and required_scope not in scopes:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    device = db_device_handler.get_device(device_id=device_id, user_id=user_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found",
        )
    return device


def _increment_session_counter(session_id: int, user_id: int) -> None:
    try:
        db_sync_session_handler.increment_operations_completed(
            session_id=session_id,
            user_id=user_id,
        )
    except Exception:
        log.warning(f"Failed to update sync session {session_id}", exc_info=True)


router = APIRouter(
    prefix="/saves",
    tags=["saves"],
)

SAVE_FILE_UPLOAD = File(..., description="Save file to upload.")
SAVE_SCREENSHOT_UPLOAD = File(
    default=None,
    description="Screenshot file associated with this save.",
)
SAVE_FILE_UPDATE = File(default=None, description="Updated save file content.")
SAVE_SCREENSHOT_UPDATE = File(default=None, description="Updated screenshot file.")


@protected_route(router.post, "", [Scope.ASSETS_WRITE])
async def add_save(
    request: Request,
    rom_id: int,
    emulator: str | None = None,
    slot: str | None = None,
    device_id: str | None = None,
    session_id: int | None = None,
    overwrite: bool = False,
    autocleanup: bool = False,
    autocleanup_limit: int = 10,
    saveFile: UploadFile = SAVE_FILE_UPLOAD,
    screenshotFile: UploadFile | None = SAVE_SCREENSHOT_UPLOAD,
) -> SaveSchema:
    """Upload a save file for a ROM."""
    device = _resolve_device(
        device_id, request.user.id, request.auth.scopes, Scope.DEVICES_WRITE
    )

    rom = db_rom_handler.get_rom(rom_id)
    if not rom:
        raise RomNotFoundInDatabaseException(rom_id)

    if not saveFile.filename:
        log.error("Save file has no filename")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Save file has no filename"
        )

    try:
        sanitized_save_filename = sanitize_filename(saveFile.filename)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid save filename: {str(exc)}",
        ) from exc

    actual_filename = sanitized_save_filename
    if slot:
        actual_filename = _apply_datetime_tag(sanitized_save_filename)

    saves_path = fs_asset_handler.build_saves_file_path(
        user=request.user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom.id,
        emulator=emulator,
    )

    db_save = db_save_handler.get_save_by_filename(
        user_id=request.user.id, rom_id=rom.id, file_name=actual_filename, slot=slot
    )

    if device and slot and not overwrite:
        slot_saves = db_save_handler.get_saves(
            user_id=request.user.id,
            rom_id=rom.id,
            slot=slot,
            order_by="updated_at",
        )
        if slot_saves:
            latest_in_slot = slot_saves[0]
            sync = db_device_save_sync_handler.get_sync(
                device_id=device.id, save_id=latest_in_slot.id
            )
            if not sync or to_utc(sync.last_synced_at) < to_utc(
                latest_in_slot.updated_at
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Slot has a newer save since your last sync",
                )
    elif device and db_save and not overwrite:
        sync = db_device_save_sync_handler.get_sync(
            device_id=device.id, save_id=db_save.id
        )
        if sync and to_utc(sync.last_synced_at) < to_utc(db_save.updated_at):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Save has been updated since your last sync",
            )

    log.info(
        f"Uploading save {hl(actual_filename)} for {hl(str(rom.name), color=BLUE)}"
    )

    await fs_asset_handler.write_file(
        file=saveFile, path=saves_path, filename=actual_filename
    )

    scanned_save = await scan_save(
        file_name=actual_filename,
        user=request.user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom_id,
        emulator=emulator,
    )

    if slot and scanned_save.content_hash and not overwrite:
        existing_by_hash = db_save_handler.get_save_by_content_hash(
            user_id=request.user.id,
            rom_id=rom.id,
            content_hash=scanned_save.content_hash,
            slot=slot,
        )
        if existing_by_hash:
            try:
                await fs_asset_handler.remove_file(f"{saves_path}/{actual_filename}")
            except FileNotFoundError:
                pass
            return _build_save_schema(
                existing_by_hash, _syncs_for_save(existing_by_hash.id, device), device
            )

    if db_save is None:
        # Refresh hash if the file already exists to avoid mismatched metadata.
        colliding_save = db_save_handler.get_save_by_path(
            user_id=request.user.id,
            rom_id=rom.id,
            file_path=scanned_save.file_path,
            file_name=actual_filename,
        )
        if colliding_save and colliding_save.content_hash != scanned_save.content_hash:
            db_save = colliding_save

    if db_save:
        # Track file path and emulator to prevent hash-content drift.
        stale_full_path = db_save.full_path
        update_data: dict = {
            "file_size_bytes": scanned_save.file_size_bytes,
            "content_hash": scanned_save.content_hash,
            "file_path": scanned_save.file_path,
            "emulator": emulator,
        }
        if slot is not None:
            update_data["slot"] = slot
        db_save = db_save_handler.update_save(db_save.id, update_data)

        # Delete orphaned bytes only if no other row references the old path.
        if stale_full_path != db_save.full_path:
            still_referenced = any(
                other.id != db_save.id and other.full_path == stale_full_path
                for other in db_save_handler.get_saves(
                    user_id=request.user.id, rom_id=rom.id
                )
            )
            if not still_referenced:
                try:
                    await fs_asset_handler.remove_file(stale_full_path)
                except FileNotFoundError:
                    pass
    else:
        scanned_save.rom_id = rom.id
        scanned_save.user_id = request.user.id
        scanned_save.emulator = emulator
        scanned_save.slot = slot
        scanned_save.origin_device_id = device.id if device else None
        db_save = db_save_handler.add_save(save=scanned_save)

    if device:
        db_device_save_sync_handler.upsert_sync(
            device_id=device.id, save_id=db_save.id, synced_at=db_save.updated_at
        )
        db_device_handler.update_last_seen(device_id=device.id, user_id=request.user.id)

    if session_id:
        _increment_session_counter(session_id, request.user.id)

    if slot and autocleanup:
        slot_saves = db_save_handler.get_saves(
            user_id=request.user.id,
            rom_id=rom.id,
            slot=slot,
            order_by="updated_at",
        )
        if len(slot_saves) > autocleanup_limit:
            for old_save in slot_saves[autocleanup_limit:]:
                db_save_handler.delete_save(old_save.id)
                try:
                    await fs_asset_handler.remove_file(old_save.full_path)
                except FileNotFoundError:
                    log.warning(f"Could not delete old save file: {old_save.full_path}")

    if screenshotFile and screenshotFile.filename:
        try:
            sanitized_screenshot_filename = sanitize_filename(screenshotFile.filename)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid screenshot filename: {str(exc)}",
            ) from exc

        screenshots_path = fs_asset_handler.build_screenshots_file_path(
            user=request.user, platform_fs_slug=rom.platform_slug, rom_id=rom.id
        )

        await fs_asset_handler.write_file(
            file=screenshotFile,
            path=screenshots_path,
            filename=sanitized_screenshot_filename,
        )

        scanned_screenshot = await scan_screenshot(
            file_name=sanitized_screenshot_filename,
            user=request.user,
            platform_fs_slug=rom.platform_slug,
            rom_id=rom.id,
        )
        db_screenshot = db_screenshot_handler.get_screenshot(
            file_name=sanitized_screenshot_filename,
            rom_id=rom.id,
            user_id=request.user.id,
        )
        if db_screenshot:
            db_screenshot = db_screenshot_handler.update_screenshot(
                db_screenshot.id,
                {"file_size_bytes": scanned_screenshot.file_size_bytes},
            )
        else:
            scanned_screenshot.rom_id = rom.id
            scanned_screenshot.user_id = request.user.id
            db_screenshot_handler.add_screenshot(screenshot=scanned_screenshot)

    rom_user = db_rom_handler.get_rom_user(rom_id=rom.id, user_id=request.user.id)
    if not rom_user:
        rom_user = db_rom_handler.add_rom_user(rom_id=rom.id, user_id=request.user.id)
    db_rom_handler.update_rom_user(
        rom_user.id, {"last_played": datetime.now(timezone.utc)}
    )

    return _build_save_schema(db_save, _syncs_for_save(db_save.id, device), device)


@protected_route(router.get, "", [Scope.ASSETS_READ])
def get_saves(
    request: Request,
    rom_id: int | None = None,
    platform_id: int | None = None,
    device_id: str | None = None,
    slot: str | None = None,
) -> list[SaveSchema]:
    """Retrieve saves for the current user."""
    device = _resolve_device(
        device_id, request.user.id, request.auth.scopes, Scope.DEVICES_READ
    )

    saves = db_save_handler.get_saves(
        user_id=request.user.id, rom_id=rom_id, platform_id=platform_id, slot=slot
    )

    if not device:
        return [_build_save_schema(save) for save in saves]

    syncs_by_save_id = db_device_save_sync_handler.get_syncs_for_saves(
        [s.id for s in saves]
    )

    return [
        _build_save_schema(save, syncs_by_save_id.get(save.id, []), device)
        for save in saves
    ]


@protected_route(router.get, "/identifiers", [Scope.ASSETS_READ])
def get_save_identifiers(request: Request) -> list[int]:
    """Retrieve save identifiers."""
    saves = db_save_handler.get_saves(
        user_id=request.user.id,
        only_fields=[Save.id],
    )

    return [save.id for save in saves]


@protected_route(router.get, "/summary", [Scope.ASSETS_READ])
def get_saves_summary(request: Request, rom_id: int) -> SaveSummarySchema:
    """Retrieve saves summary grouped by slot."""
    summary_data = db_save_handler.get_saves_summary(
        user_id=request.user.id, rom_id=rom_id
    )

    slots = [
        SlotSummarySchema(
            slot=slot_data["slot"],
            count=slot_data["count"],
            latest=_build_save_schema(slot_data["latest"]),
        )
        for slot_data in summary_data["slots"]
    ]

    return SaveSummarySchema(total_count=summary_data["total_count"], slots=slots)


@protected_route(router.get, "/{id}", [Scope.ASSETS_READ])
def get_save(request: Request, id: int, device_id: str | None = None) -> SaveSchema:
    """Retrieve a save by ID."""
    device = _resolve_device(
        device_id, request.user.id, request.auth.scopes, Scope.DEVICES_READ
    )

    save = db_save_handler.get_save(user_id=request.user.id, id=id)
    if not save:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Save with ID {id} not found",
        )

    return _build_save_schema(save, _syncs_for_save(save.id, device), device)


@protected_route(router.get, "/{id}/content", [Scope.ASSETS_READ])
def download_save(
    request: Request,
    id: int,
    device_id: str | None = None,
    session_id: int | None = None,
    optimistic: bool = True,
) -> FileResponse:
    """Download a save file."""
    device = _resolve_device(
        device_id, request.user.id, request.auth.scopes, Scope.DEVICES_READ
    )

    # Owner can download any of their saves; everyone else only public ones.
    save = db_save_handler.get_save_by_id(id)
    if not save or (save.user_id != request.user.id and not save.is_public):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Save with ID {id} not found",
        )
    is_owner = save.user_id == request.user.id

    try:
        file_path = fs_asset_handler.validate_path(save.full_path)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Save file not found",
        ) from None

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Save file not found on disk",
        )

    # Sync bookkeeping only makes sense for the owner's own saves.
    if device and optimistic and is_owner:
        db_device_save_sync_handler.upsert_sync(
            device_id=device.id,
            save_id=save.id,
            synced_at=save.updated_at,
        )
        db_device_handler.update_last_seen(device_id=device.id, user_id=request.user.id)

    if session_id:
        _increment_session_counter(session_id, request.user.id)

    return FileResponse(path=str(file_path), filename=save.file_name)


@protected_route(router.post, "/{id}/downloaded", [Scope.DEVICES_WRITE])
def confirm_download(
    request: Request,
    id: int,
    device_id: str = Body(..., embed=True),
) -> SaveSchema:
    """Confirm a save was downloaded successfully."""
    save = db_save_handler.get_save(user_id=request.user.id, id=id)
    if not save:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Save with ID {id} not found",
        )

    device = _resolve_device(device_id, request.user.id)
    db_device_save_sync_handler.upsert_sync(
        device_id=device_id,
        save_id=save.id,
        synced_at=save.updated_at,
    )
    db_device_handler.update_last_seen(device_id=device_id, user_id=request.user.id)

    return _build_save_schema(save, _syncs_for_save(save.id, device), device)


@protected_route(router.put, "/{id}", [Scope.ASSETS_WRITE])
async def update_save(
    request: Request,
    id: int,
    device_id: str | None = None,
    saveFile: UploadFile | None = SAVE_FILE_UPDATE,
    screenshotFile: UploadFile | None = SAVE_SCREENSHOT_UPDATE,
) -> SaveSchema:
    """Update a save file."""

    device = _resolve_device(
        device_id, request.user.id, request.auth.scopes, Scope.DEVICES_WRITE
    )

    db_save = db_save_handler.get_save(user_id=request.user.id, id=id)
    if not db_save:
        error = f"Save with ID {id} not found"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    if saveFile:
        await fs_asset_handler.write_file(
            file=saveFile, path=db_save.file_path, filename=db_save.file_name
        )
        scanned_save = await scan_save(
            file_name=db_save.file_name,
            user=request.user,
            platform_fs_slug=db_save.rom.platform_fs_slug,
            rom_id=db_save.rom_id,
            emulator=db_save.emulator,
        )
        db_save = db_save_handler.update_save(
            db_save.id,
            {
                "file_size_bytes": scanned_save.file_size_bytes,
                "content_hash": scanned_save.content_hash,
            },
        )

    if screenshotFile and screenshotFile.filename:
        try:
            sanitized_screenshot_filename = sanitize_filename(screenshotFile.filename)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid screenshot filename: {str(exc)}",
            ) from exc

        screenshots_path = fs_asset_handler.build_screenshots_file_path(
            user=request.user,
            platform_fs_slug=db_save.rom.platform_slug,
            rom_id=db_save.rom.id,
        )

        await fs_asset_handler.write_file(
            file=screenshotFile,
            path=screenshots_path,
            filename=sanitized_screenshot_filename,
        )

        # Scan or update screenshot
        scanned_screenshot = await scan_screenshot(
            file_name=sanitized_screenshot_filename,
            user=request.user,
            platform_fs_slug=db_save.rom.platform_slug,
            rom_id=db_save.rom.id,
        )
        db_screenshot = db_screenshot_handler.get_screenshot(
            file_name=sanitized_screenshot_filename,
            rom_id=db_save.rom.id,
            user_id=request.user.id,
        )
        if db_screenshot:
            db_screenshot = db_screenshot_handler.update_screenshot(
                db_screenshot.id,
                {"file_size_bytes": scanned_screenshot.file_size_bytes},
            )
        else:
            scanned_screenshot.rom_id = db_save.rom.id
            scanned_screenshot.user_id = request.user.id
            db_screenshot_handler.add_screenshot(screenshot=scanned_screenshot)

    # Set the last played time for the current user
    rom_user = db_rom_handler.get_rom_user(db_save.rom_id, request.user.id)
    if not rom_user:
        rom_user = db_rom_handler.add_rom_user(db_save.rom_id, request.user.id)
    db_rom_handler.update_rom_user(
        rom_user.id, {"last_played": datetime.now(timezone.utc)}
    )

    if device:
        db_device_save_sync_handler.upsert_sync(
            device_id=device.id, save_id=db_save.id, synced_at=db_save.updated_at
        )
        db_device_handler.update_last_seen(device_id=device.id, user_id=request.user.id)

    return _build_save_schema(db_save, _syncs_for_save(db_save.id, device), device)


@protected_route(
    router.put,
    "/{id}/visibility",
    [Scope.ASSETS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
def update_save_visibility(
    request: Request,
    id: int,
    is_public: Annotated[bool, Body(embed=True)],
) -> SaveSchema:
    """Toggle a save's public/private visibility (owner only)."""
    save = db_save_handler.get_save_by_id(id)
    if not save or save.user_id != request.user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Save with ID {id} not found",
        )

    updated = db_save_handler.update_save(id, {"is_public": is_public})

    # Keep the auto-captured thumbnail's visibility in sync so a shared save
    # still renders its preview for other users.
    if save.screenshot:
        db_screenshot_handler.update_screenshot(
            save.screenshot.id, {"is_public": is_public}
        )

    return _build_save_schema(updated)


@protected_route(
    router.post,
    "/delete",
    [Scope.ASSETS_WRITE],
    responses={
        status.HTTP_400_BAD_REQUEST: {},
        status.HTTP_404_NOT_FOUND: {},
    },
)
async def delete_saves(
    request: Request,
    saves: Annotated[
        list[int],
        Body(
            description="List of save ids to delete from database.",
            embed=True,
        ),
    ],
) -> list[int]:
    """Delete saves."""
    if not saves:
        error = "No saves were provided"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    for save_id in saves:
        save = db_save_handler.get_save(user_id=request.user.id, id=save_id)
        if not save:
            error = f"Save with ID {save_id} not found"
            log.error(error)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

        db_save_handler.delete_save(save_id)

        log.info(
            f"Deleting save {hl(save.file_name)} [{save.rom.platform_slug}] from filesystem"
        )
        try:
            file_path = f"{save.file_path}/{save.file_name}"
            await fs_asset_handler.remove_file(file_path=file_path)
        except FileNotFoundError:
            error = f"Save file {hl(save.file_name)} not found for platform {hl(save.rom.platform_display_name, color=BLUE)}[{hl(save.rom.platform_slug)}]"
            log.error(error)

        if save.screenshot:
            db_screenshot_handler.delete_screenshot(save.screenshot.id)

            try:
                file_path = f"{save.screenshot.file_path}/{save.screenshot.file_name}"
                await fs_asset_handler.remove_file(file_path=file_path)
            except FileNotFoundError:
                error = f"Screenshot file {hl(save.screenshot.file_name)} not found for save {hl(save.file_name)}[{hl(save.rom.platform_slug)}]"
                log.error(error)

    return saves


@protected_route(router.post, "/{id}/track", [Scope.DEVICES_WRITE])
def track_save(
    request: Request,
    id: int,
    device_id: str = Body(..., embed=True),
) -> SaveSchema:
    """Re-enable sync tracking for a save on a device."""
    save = db_save_handler.get_save(user_id=request.user.id, id=id)
    if not save:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Save with ID {id} not found",
        )

    device = _resolve_device(device_id, request.user.id)
    db_device_save_sync_handler.set_untracked(
        device_id=device_id, save_id=id, untracked=False
    )

    return _build_save_schema(save, _syncs_for_save(save.id, device), device)


@protected_route(router.post, "/{id}/untrack", [Scope.DEVICES_WRITE])
def untrack_save(
    request: Request,
    id: int,
    device_id: str = Body(..., embed=True),
) -> SaveSchema:
    """Disable sync tracking for a save on a device."""
    save = db_save_handler.get_save(user_id=request.user.id, id=id)
    if not save:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Save with ID {id} not found",
        )

    device = _resolve_device(device_id, request.user.id)
    db_device_save_sync_handler.set_untracked(
        device_id=device_id, save_id=id, untracked=True
    )

    return _build_save_schema(save, _syncs_for_save(save.id, device), device)
