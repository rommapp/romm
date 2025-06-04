from datetime import datetime, timezone

from decorators.auth import protected_route
from endpoints.responses.assets import SaveSchema
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from fastapi import HTTPException, Request, UploadFile, status
from handler.auth.constants import Scope
from handler.database import db_rom_handler, db_save_handler, db_screenshot_handler
from handler.filesystem import fs_asset_handler
from handler.scan_handler import scan_save, scan_screenshot
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from utils.router import APIRouter

router = APIRouter(
    prefix="/saves",
    tags=["saves"],
)


@protected_route(router.post, "", [Scope.ASSETS_WRITE])
async def add_save(
    request: Request,
    rom_id: int,
    emulator: str | None = None,
) -> SaveSchema:
    data = await request.form()

    rom = db_rom_handler.get_rom(rom_id)
    if not rom:
        raise RomNotFoundInDatabaseException(rom_id)

    log.info(f"Uploading save of {rom.name}")

    saves_path = fs_asset_handler.build_saves_file_path(
        user=request.user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom_id,
        emulator=emulator,
    )

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

    rom = db_rom_handler.get_rom(rom_id)
    if not rom:
        raise RomNotFoundInDatabaseException(rom_id)

    log.info(f"Uploading save {hl(saveFile.filename)} for {hl(rom.name, color=BLUE)}")

    saves_path = fs_asset_handler.build_saves_file_path(
        user=request.user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom.id,
        emulator=emulator,
    )

    fs_asset_handler.write_file(file=saveFile, path=saves_path)

    # Scan or update save
    scanned_save = scan_save(
        file_name=saveFile.filename,
        user=request.user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom_id,
        emulator=emulator,
    )
    db_save = db_save_handler.get_save_by_filename(
        user_id=request.user.id, rom_id=rom.id, file_name=saveFile.filename
    )
    if db_save:
        db_save = db_save_handler.update_save(
            db_save.id, {"file_size_bytes": scanned_save.file_size_bytes}
        )
    else:
        scanned_save.rom_id = rom.id
        scanned_save.user_id = request.user.id
        scanned_save.emulator = emulator
        db_save = db_save_handler.add_save(save=scanned_save)

    screenshotFile: UploadFile | None = data.get("screenshotFile", None)  # type: ignore
    if screenshotFile and screenshotFile.filename:
        screenshots_path = fs_asset_handler.build_screenshots_file_path(
            user=request.user, platform_fs_slug=rom.platform_slug, rom_id=rom.id
        )

        fs_asset_handler.write_file(file=screenshotFile, path=screenshots_path)

        # Scan or update screenshot
        scanned_screenshot = scan_screenshot(
            file_name=screenshotFile.filename,
            user=request.user,
            platform_fs_slug=rom.platform_slug,
            rom_id=rom.id,
        )
        db_screenshot = db_screenshot_handler.get_screenshot_by_filename(
            rom_id=rom.id, user_id=request.user.id, file_name=screenshotFile.filename
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

    # Set the last played time for the current user
    rom_user = db_rom_handler.get_rom_user(rom_id=rom.id, user_id=request.user.id)
    if not rom_user:
        rom_user = db_rom_handler.add_rom_user(rom_id=rom.id, user_id=request.user.id)
    db_rom_handler.update_rom_user(
        rom_user.id, {"last_played": datetime.now(timezone.utc)}
    )

    # Refetch the rom to get updated saves
    rom = db_rom_handler.get_rom(rom_id)
    if not rom:
        raise RomNotFoundInDatabaseException(rom_id)

    return SaveSchema.model_validate(db_save)


@protected_route(router.get, "", [Scope.ASSETS_READ])
def get_saves(
    request: Request, rom_id: int | None = None, platform_id: int | None = None
) -> list[SaveSchema]:
    saves = db_save_handler.get_saves(
        user_id=request.user.id, rom_id=rom_id, platform_id=platform_id
    )

    return [SaveSchema.model_validate(save) for save in saves]


@protected_route(router.get, "/{id}", [Scope.ASSETS_READ])
def get_save(request: Request, id: int) -> SaveSchema:
    save = db_save_handler.get_save(user_id=request.user.id, id=id)

    if not save:
        error = f"Save with ID {id} not found"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    return SaveSchema.model_validate(save)


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
        fs_asset_handler.write_file(file=saveFile, path=db_save.file_path)
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

        fs_asset_handler.write_file(file=screenshotFile, path=screenshots_path)

        # Scan or update screenshot
        scanned_screenshot = scan_screenshot(
            file_name=screenshotFile.filename,
            user=request.user,
            platform_fs_slug=db_save.rom.platform_slug,
            rom_id=db_save.rom.id,
        )
        db_screenshot = db_screenshot_handler.get_screenshot_by_filename(
            rom_id=db_save.rom.id,
            user_id=request.user.id,
            file_name=screenshotFile.filename,
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


@protected_route(router.post, "/delete", [Scope.ASSETS_WRITE])
async def delete_saves(request: Request) -> list[int]:
    data: dict = await request.json()
    save_ids: list = data["saves"]

    if not save_ids:
        error = "No saves were provided"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    for save_id in save_ids:
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
            fs_asset_handler.remove_file(
                file_name=save.file_name, file_path=save.file_path
            )
        except FileNotFoundError:
            error = f"Save file {hl(save.file_name)} not found for platform {hl(save.rom.platform_display_name, color=BLUE)}[{hl(save.rom.platform_slug)}]"
            log.error(error)

        if save.screenshot:
            db_screenshot_handler.delete_screenshot(save.screenshot.id)

            try:
                fs_asset_handler.remove_file(
                    file_name=save.screenshot.file_name,
                    file_path=save.screenshot.file_path,
                )
            except FileNotFoundError:
                error = f"Screenshot file {hl(save.screenshot.file_name)} not found for save {hl(save.file_name)}[{hl(save.rom.platform_slug)}]"
                log.error(error)

    return save_ids
