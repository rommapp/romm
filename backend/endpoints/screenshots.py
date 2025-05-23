from decorators.auth import protected_route
from endpoints.responses.assets import ScreenshotSchema
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from fastapi import HTTPException, Request, UploadFile, status
from handler.auth.constants import Scope
from handler.database import db_rom_handler, db_screenshot_handler
from handler.filesystem import fs_asset_handler
from handler.scan_handler import scan_screenshot
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from utils.router import APIRouter

router = APIRouter(
    prefix="/screenshots",
    tags=["screenshots"],
)


@protected_route(router.post, "", [Scope.ASSETS_WRITE])
async def add_screenshot(
    request: Request,
    rom_id: int,
) -> ScreenshotSchema:
    data = await request.form()

    rom = db_rom_handler.get_rom(id=rom_id)
    if not rom:
        raise RomNotFoundInDatabaseException(rom_id)

    current_user = request.user
    log.info(f"Uploading screenshots to {hl(rom.name, color=BLUE)}")

    screenshots_path = fs_asset_handler.build_screenshots_file_path(
        user=request.user, platform_fs_slug=rom.platform_slug, rom_id=rom.id
    )

    if "screenshotFile" not in data:
        log.error("No screenshot file provided")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No screenshot file provided",
        )

    screenshotFile: UploadFile = data["screenshotFile"]  # type: ignore
    if not screenshotFile.filename:
        log.error("Screenshot file has no filename")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Screenshot file has no filename",
        )

    if not screenshotFile.filename:
        log.warning("Skipping empty screenshot")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Screenshot has no filename"
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
        rom_id=rom.id, user_id=current_user.id, file_name=screenshotFile.filename
    )
    if db_screenshot:
        db_screenshot = db_screenshot_handler.update_screenshot(
            db_screenshot.id,
            {"file_size_bytes": scanned_screenshot.file_size_bytes},
        )
    else:
        scanned_screenshot.rom_id = rom.id
        scanned_screenshot.user_id = current_user.id
        db_screenshot = db_screenshot_handler.add_screenshot(
            screenshot=scanned_screenshot
        )

    rom = db_rom_handler.get_rom(id=rom_id)
    if not rom:
        raise RomNotFoundInDatabaseException(rom_id)

    return ScreenshotSchema.model_validate(db_screenshot)
