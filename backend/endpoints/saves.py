import os
import re
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Body, HTTPException, Request, UploadFile, status
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
from utils.router import APIRouter


def _build_save_schema(
    save: Save,
    device: Device | None = None,
    sync: DeviceSaveSync | None = None,
) -> SaveSchema:
    save_schema = SaveSchema.model_validate(save)

    if device:
        if sync:
            is_current = to_utc(sync.last_synced_at) >= to_utc(save.updated_at)
            last_synced = sync.last_synced_at
            is_untracked = sync.is_untracked
        else:
            is_current = False
            last_synced = save.updated_at
            is_untracked = False

        save_schema.device_syncs = [
            DeviceSyncSchema(
                device_id=device.id,
                device_name=device.name,
                last_synced_at=last_synced,
                is_untracked=is_untracked,
                is_current=is_current,
            )
        ]

    return save_schema


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


router = APIRouter(
    prefix="/saves",
    tags=["saves"],
)


@protected_route(router.post, "", [Scope.ASSETS_WRITE])
async def add_save(
    request: Request,
    rom_id: int,
    emulator: str | None = None,
    slot: str | None = None,
    device_id: str | None = None,
    overwrite: bool = False,
    autocleanup: bool = False,
    autocleanup_limit: int = 10,
) -> SaveSchema:
    """Upload a save file for a ROM."""
    device = _resolve_device(
        device_id, request.user.id, request.auth.scopes, Scope.DEVICES_WRITE
    )

    data = await request.form()

    rom = db_rom_handler.get_rom(rom_id)
    if not rom:
        raise RomNotFoundInDatabaseException(rom_id)

    if "saveFile" not in data:
        log.error("No save file provided")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No save file provided"
        )

    saveFile: UploadFile = data["saveFile"]  # type: ignore

    if not saveFile.filename:
        log.error("Save file has no filename")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Save file has no filename"
        )

    actual_filename = saveFile.filename
    if slot:
        actual_filename = _apply_datetime_tag(saveFile.filename)

    db_save = db_save_handler.get_save_by_filename(
        user_id=request.user.id, rom_id=rom.id, file_name=actual_filename
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

    saves_path = fs_asset_handler.build_saves_file_path(
        user=request.user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom.id,
        emulator=emulator,
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
        )
        if existing_by_hash:
            try:
                await fs_asset_handler.remove_file(f"{saves_path}/{actual_filename}")
            except FileNotFoundError:
                pass
            sync = None
            if device:
                sync = db_device_save_sync_handler.get_sync(
                    device_id=device.id, save_id=existing_by_hash.id
                )
            return _build_save_schema(existing_by_hash, device, sync)

    if db_save:
        update_data: dict = {
            "file_size_bytes": scanned_save.file_size_bytes,
            "content_hash": scanned_save.content_hash,
        }
        if slot is not None:
            update_data["slot"] = slot
        db_save = db_save_handler.update_save(db_save.id, update_data)
    else:
        scanned_save.rom_id = rom.id
        scanned_save.user_id = request.user.id
        scanned_save.emulator = emulator
        scanned_save.slot = slot
        db_save = db_save_handler.add_save(save=scanned_save)

    if device:
        db_device_save_sync_handler.upsert_sync(
            device_id=device.id, save_id=db_save.id, synced_at=db_save.updated_at
        )
        db_device_handler.update_last_seen(device_id=device.id, user_id=request.user.id)

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

    screenshotFile: UploadFile | None = data.get("screenshotFile", None)  # type: ignore
    if screenshotFile and screenshotFile.filename:
        screenshots_path = fs_asset_handler.build_screenshots_file_path(
            user=request.user, platform_fs_slug=rom.platform_slug, rom_id=rom.id
        )

        await fs_asset_handler.write_file(file=screenshotFile, path=screenshots_path)

        scanned_screenshot = await scan_screenshot(
            file_name=screenshotFile.filename,
            user=request.user,
            platform_fs_slug=rom.platform_slug,
            rom_id=rom.id,
        )
        db_screenshot = db_screenshot_handler.get_screenshot(
            file_name=screenshotFile.filename,
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

    sync = None
    if device:
        sync = db_device_save_sync_handler.get_sync(
            device_id=device.id, save_id=db_save.id
        )
    return _build_save_schema(db_save, device, sync)


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

    syncs = db_device_save_sync_handler.get_syncs_for_device_and_saves(
        device_id=device.id, save_ids=[s.id for s in saves]
    )
    sync_by_save_id = {s.save_id: s for s in syncs}

    return [
        _build_save_schema(save, device, sync_by_save_id.get(save.id)) for save in saves
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

    sync = None
    if device:
        sync = db_device_save_sync_handler.get_sync(
            device_id=device.id, save_id=save.id
        )
    return _build_save_schema(save, device, sync)


@protected_route(router.get, "/{id}/content", [Scope.ASSETS_READ])
def download_save(
    request: Request,
    id: int,
    device_id: str | None = None,
    optimistic: bool = True,
) -> FileResponse:
    """Download a save file."""
    device = _resolve_device(
        device_id, request.user.id, request.auth.scopes, Scope.DEVICES_READ
    )

    save = db_save_handler.get_save(user_id=request.user.id, id=id)
    if not save:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Save with ID {id} not found",
        )

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

    if device and optimistic:
        db_device_save_sync_handler.upsert_sync(
            device_id=device.id,
            save_id=save.id,
            synced_at=save.updated_at,
        )
        db_device_handler.update_last_seen(device_id=device.id, user_id=request.user.id)

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
    sync = db_device_save_sync_handler.upsert_sync(
        device_id=device_id,
        save_id=save.id,
        synced_at=save.updated_at,
    )
    db_device_handler.update_last_seen(device_id=device_id, user_id=request.user.id)

    return _build_save_schema(save, device, sync)


@protected_route(router.put, "/{id}", [Scope.ASSETS_WRITE])
async def update_save(request: Request, id: int) -> SaveSchema:
    """Update a save file."""
    data = await request.form()

    db_save = db_save_handler.get_save(user_id=request.user.id, id=id)
    if not db_save:
        error = f"Save with ID {id} not found"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    if "saveFile" in data:
        saveFile: UploadFile = data["saveFile"]  # type: ignore
        await fs_asset_handler.write_file(file=saveFile, path=db_save.file_path)
        db_save = db_save_handler.update_save(
            db_save.id, {"file_size_bytes": saveFile.size}
        )

    screenshotFile: UploadFile | None = data.get("screenshotFile", None)  # type: ignore
    if screenshotFile and screenshotFile.filename:
        screenshots_path = fs_asset_handler.build_screenshots_file_path(
            user=request.user,
            platform_fs_slug=db_save.rom.platform_slug,
            rom_id=db_save.rom.id,
        )

        await fs_asset_handler.write_file(file=screenshotFile, path=screenshots_path)

        # Scan or update screenshot
        scanned_screenshot = await scan_screenshot(
            file_name=screenshotFile.filename,
            user=request.user,
            platform_fs_slug=db_save.rom.platform_slug,
            rom_id=db_save.rom.id,
        )
        db_screenshot = db_screenshot_handler.get_screenshot(
            file_name=screenshotFile.filename,
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

    # Refetch the save to get updated fields
    return SaveSchema.model_validate(db_save)


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
    sync = db_device_save_sync_handler.set_untracked(
        device_id=device_id, save_id=id, untracked=False
    )

    return _build_save_schema(save, device, sync)


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
    sync = db_device_save_sync_handler.set_untracked(
        device_id=device_id, save_id=id, untracked=True
    )

    return _build_save_schema(save, device, sync)
