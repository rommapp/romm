from config.config_manager import config_manager as cm
from decorators.auth import protected_route
from endpoints.responses.assets import UploadedScreenshotsResponse
from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from handler import db_screenshot_handler, fs_asset_handler, db_rom_handler
from handler.scan_handler import scan_screenshot
from logger.logger import log

router = APIRouter()


@protected_route(router.post, "/screenshots", ["assets.write"])
def add_screenshots(
    request: Request, rom_id: int, screenshots: list[UploadFile] = File(...)
) -> UploadedScreenshotsResponse:
    rom = db_rom_handler.get_roms(rom_id)
    log.info(f"Uploading screenshots to {rom.name}")
    if screenshots is None:
        log.error("No screenshots were uploaded")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No screenshots were uploaded",
        )

    screenshots_path = fs_asset_handler.build_upload_file_path(
        rom.platform.fs_slug, folder=cm.config.SCREENSHOTS_FOLDER_NAME
    )

    for screenshot in screenshots:
        fs_asset_handler._write_file(file=screenshot, path=screenshots_path)

        # Scan or update screenshot
        scanned_screenshot = scan_screenshot(
            file_name=screenshot.filename, platform=rom.platform
        )
        db_screenshot = db_screenshot_handler.get_screenshot_by_filename(
            file_name=screenshot.filename, rom_id=rom.id
        )
        if db_screenshot:
            db_screenshot_handler.update_screenshot(
                db_screenshot.id,
                {"file_size_bytes": scanned_screenshot.file_size_bytes},
            )
            continue

        scanned_screenshot.rom_id = rom.id
        db_screenshot_handler.add_screenshot(scanned_screenshot)

    rom = db_rom_handler.get_roms(rom_id)
    return {
        "uploaded": len(screenshots),
        "screenshots": rom.screenshots,
        "url_screenshots": rom.url_screenshots,
        "merged_screenshots": rom.merged_screenshots,
    }
