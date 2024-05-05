from decorators.auth import protected_route
from endpoints.responses.assets import UploadedScreenshotsResponse
from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from handler.database import db_roms_handler, db_screenshots_handler
from handler.filesystem import fs_assets_handler
from handler.scan_handler import scan_screenshot
from logger.logger import log

router = APIRouter()


@protected_route(router.post, "/screenshots", ["assets.write"])
def add_screenshots(
    request: Request, rom_id: int, screenshots: list[UploadFile] = File(...)
) -> UploadedScreenshotsResponse:
    rom = db_roms_handler.get_roms(rom_id)
    current_user = request.user
    log.info(f"Uploading screenshots to {rom.name}")

    if screenshots is None:
        log.error("No screenshots were uploaded")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No screenshots were uploaded",
        )

    screenshots_path = fs_assets_handler.build_screenshots_file_path(
        user=request.user, platform_fs_slug=rom.platform_slug
    )

    for screenshot in screenshots:
        fs_assets_handler.write_file(file=screenshot, path=screenshots_path)

        # Scan or update screenshot
        scanned_screenshot = scan_screenshot(
            file_name=screenshot.filename,
            user=request.user,
            platform_fs_slug=rom.platform_slug,
        )
        db_screenshot = db_screenshots_handler.get_screenshot_by_filename(
            rom_id=rom.id, user_id=current_user.id, file_name=screenshot.filename
        )
        if db_screenshot:
            db_screenshots_handler.update_screenshot(
                db_screenshot.id,
                {"file_size_bytes": scanned_screenshot.file_size_bytes},
            )
            continue

        scanned_screenshot.rom_id = rom.id
        scanned_screenshot.user_id = current_user.id
        db_screenshots_handler.add_screenshot(scanned_screenshot)

    rom = db_roms_handler.get_roms(rom_id)
    return {
        "uploaded": len(screenshots),
        "screenshots": [s for s in rom.screenshots if s.user_id == current_user.id],
        "url_screenshots": rom.url_screenshots,
        "merged_screenshots": rom.merged_screenshots,
    }
