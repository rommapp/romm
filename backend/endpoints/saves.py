from datetime import datetime, timezone
from typing import Annotated

from fastapi import Body, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse

from decorators.auth import protected_route
from endpoints.responses.assets import SaveSchema
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
from utils.router import APIRouter


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _build_save_schema(
    save: Save,
    device: Device | None = None,
    sync: DeviceSaveSync | None = None,
) -> SaveSchema:
    device_syncs: list[DeviceSyncSchema] = []

    if device:
        last_synced = sync.last_synced_at if sync else save.updated_at
        is_current = _to_utc(last_synced) >= _to_utc(save.updated_at)
        device_syncs.append(
            DeviceSyncSchema(
                device_id=device.id,
                device_name=device.name,
                last_synced_at=last_synced,
                is_untracked=sync.is_untracked if sync else False,
                is_current=is_current,
            )
        )

    save_data = {
        key: getattr(save, key)
        for key in SaveSchema.model_fields
        if key != "device_syncs" and hasattr(save, key)
    }
    save_data["device_syncs"] = device_syncs
    return SaveSchema.model_validate(save_data)


router = APIRouter(
    prefix="/saves",
    tags=["saves"],
)


@protected_route(router.post, "", [Scope.ASSETS_WRITE])
async def add_save(
    request: Request,
    rom_id: int,
    emulator: str | None = None,
    save_name: str | None = None,
    device_id: str | None = None,
    overwrite: bool = False,
) -> SaveSchema:
    if device_id and Scope.DEVICES_WRITE not in request.auth.scopes:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    device = None
    if device_id:
        device = db_device_handler.get_device(
            device_id=device_id, user_id=request.user.id
        )
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Device with ID {device_id} not found",
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

    db_save = db_save_handler.get_save_by_filename(
        user_id=request.user.id, rom_id=rom.id, file_name=saveFile.filename
    )

    if device and db_save and not overwrite:
        sync = db_device_save_sync_handler.get_sync(
            device_id=device.id, save_id=db_save.id
        )
        if sync and sync.last_synced_at < db_save.updated_at:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "conflict",
                    "message": "Save has been updated since last sync",
                    "save_id": db_save.id,
                    "current_save_time": db_save.updated_at.isoformat(),
                    "device_sync_time": sync.last_synced_at.isoformat(),
                },
            )

    log.info(
        f"Uploading save {hl(saveFile.filename)} for {hl(str(rom.name), color=BLUE)}"
    )

    saves_path = fs_asset_handler.build_saves_file_path(
        user=request.user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom.id,
        emulator=emulator,
    )

    await fs_asset_handler.write_file(file=saveFile, path=saves_path)

    scanned_save = await scan_save(
        file_name=saveFile.filename,
        user=request.user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom_id,
        emulator=emulator,
    )

    if db_save:
        db_save = db_save_handler.update_save(
            db_save.id,
            {
                "file_size_bytes": scanned_save.file_size_bytes,
                "save_name": save_name or db_save.save_name,
            },
        )
    else:
        scanned_save.rom_id = rom.id
        scanned_save.user_id = request.user.id
        scanned_save.emulator = emulator
        scanned_save.save_name = save_name
        db_save = db_save_handler.add_save(save=scanned_save)

    if device:
        db_device_save_sync_handler.upsert_sync(
            device_id=device.id, save_id=db_save.id, synced_at=db_save.updated_at
        )
        db_device_handler.update_last_seen(device_id=device.id, user_id=request.user.id)

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
            filename=screenshotFile.filename,
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
) -> list[SaveSchema]:
    if device_id and Scope.DEVICES_READ not in request.auth.scopes:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    device = None
    if device_id:
        device = db_device_handler.get_device(
            device_id=device_id, user_id=request.user.id
        )
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Device with ID {device_id} not found",
            )

    saves = db_save_handler.get_saves(
        user_id=request.user.id, rom_id=rom_id, platform_id=platform_id
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
def get_save_identifiers(
    request: Request,
) -> list[int]:
    """Get save identifiers endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        list[int]: List of save IDs
    """
    saves = db_save_handler.get_saves(
        user_id=request.user.id,
        only_fields=[Save.id],
    )

    return [save.id for save in saves]


@protected_route(router.get, "/{id}", [Scope.ASSETS_READ])
def get_save(request: Request, id: int, device_id: str | None = None) -> SaveSchema:
    if device_id and Scope.DEVICES_READ not in request.auth.scopes:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    device = None
    if device_id:
        device = db_device_handler.get_device(
            device_id=device_id, user_id=request.user.id
        )
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Device with ID {device_id} not found",
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
    if device_id and Scope.DEVICES_READ not in request.auth.scopes:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    device = None
    if device_id:
        device = db_device_handler.get_device(
            device_id=device_id, user_id=request.user.id
        )
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Device with ID {device_id} not found",
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

    save = db_save_handler.get_save(user_id=request.user.id, id=id)
    if not save:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Save with ID {id} not found",
        )

    device = db_device_handler.get_device(device_id=device_id, user_id=request.user.id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found",
        )

    sync = db_device_save_sync_handler.upsert_sync(
        device_id=device_id,
        save_id=save.id,
        synced_at=save.updated_at,
    )
    db_device_handler.update_last_seen(device_id=device_id, user_id=request.user.id)

    return _build_save_schema(save, device, sync)


@protected_route(router.put, "/{id}", [Scope.ASSETS_WRITE])
async def update_save(request: Request, id: int) -> SaveSchema:
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
            filename=screenshotFile.filename,
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

    save = db_save_handler.get_save(user_id=request.user.id, id=id)
    if not save:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Save with ID {id} not found",
        )

    device = db_device_handler.get_device(device_id=device_id, user_id=request.user.id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found",
        )

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

    save = db_save_handler.get_save(user_id=request.user.id, id=id)
    if not save:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Save with ID {id} not found",
        )

    device = db_device_handler.get_device(device_id=device_id, user_id=request.user.id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found",
        )

    sync = db_device_save_sync_handler.set_untracked(
        device_id=device_id, save_id=id, untracked=True
    )

    return _build_save_schema(save, device, sync)
