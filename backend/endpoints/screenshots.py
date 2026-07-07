from typing import Annotated

from fastapi import Body, File, HTTPException
from fastapi import Path as PathVar
from fastapi import Request, UploadFile, status
from fastapi.responses import FileResponse, Response

from decorators.auth import protected_route
from endpoints.responses.assets import ScreenshotSchema
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from handler.auth.constants import Scope
from handler.database import db_rom_handler, db_screenshot_handler
from handler.filesystem import fs_asset_handler
from handler.filesystem.assets_handler import build_asset_file_response
from handler.scan_handler import scan_screenshot
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from utils.filesystem import sanitize_filename
from utils.media_types import (
    ALLOWED_IMAGE_EXTENSIONS,
    is_inline_media_file,
)
from utils.router import APIRouter

router = APIRouter(
    prefix="/screenshots",
    tags=["screenshots"],
)

SCREENSHOT_FILE_UPLOAD = File(..., description="Screenshot file to upload.")


@protected_route(router.post, "", [Scope.ASSETS_WRITE])
async def add_screenshot(
    request: Request,
    rom_id: int,
    screenshotFile: UploadFile = SCREENSHOT_FILE_UPLOAD,
) -> ScreenshotSchema:
    """Upload a per-user gallery screenshot for a ROM.

    Stored under the user's asset folder (not the ROM folder) and flagged
    `is_gallery=True` so it surfaces in the gallery; `is_public=False` so it
    stays private until the owner shares it.
    """
    rom = db_rom_handler.get_rom(id=rom_id)
    if not rom:
        raise RomNotFoundInDatabaseException(rom_id)

    current_user = request.user
    log.info(f"Uploading screenshot to {hl(str(rom.name), color=BLUE)}")

    screenshots_path = fs_asset_handler.build_screenshots_file_path(
        user=request.user, platform_fs_slug=rom.platform_slug, rom_id=rom.id
    )

    if not screenshotFile.filename:
        log.error("Screenshot file has no filename")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Screenshot file has no filename",
        )

    try:
        sanitized_screenshot_filename = sanitize_filename(screenshotFile.filename)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid screenshot filename: {str(exc)}",
        ) from exc

    if not is_inline_media_file(sanitized_screenshot_filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported image file type. Allowed: "
                f"{', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}"
            ),
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
        platform_fs_slug=rom.platform_slug,
        rom_id=rom.id,
    )
    db_screenshot = db_screenshot_handler.get_screenshot(
        file_name=sanitized_screenshot_filename,
        rom_id=rom.id,
        user_id=current_user.id,
    )
    if db_screenshot:
        db_screenshot = db_screenshot_handler.update_screenshot(
            db_screenshot.id,
            {
                "file_size_bytes": scanned_screenshot.file_size_bytes,
                "is_gallery": True,
                "missing_from_fs": False,
            },
        )
    else:
        scanned_screenshot.rom_id = rom.id
        scanned_screenshot.user_id = current_user.id
        scanned_screenshot.is_gallery = True
        db_screenshot = db_screenshot_handler.add_screenshot(
            screenshot=scanned_screenshot
        )

    return ScreenshotSchema.model_validate(db_screenshot)


@protected_route(
    router.get,
    "/{id}/content",
    [Scope.ASSETS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
def download_screenshot(
    request: Request,
    id: Annotated[int, PathVar(description="Screenshot internal id.", ge=1)],
) -> FileResponse:
    """Download a screenshot file. Owner can download any of their screenshots;
    everyone else only public ones."""
    screenshot = db_screenshot_handler.get_screenshot_by_id(id)
    if not screenshot or (
        screenshot.user_id != request.user.id and not screenshot.is_public
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Screenshot not found",
        )

    try:
        file_path = fs_asset_handler.validate_path(screenshot.full_path)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Screenshot not found",
        ) from None

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Screenshot file not found on disk",
        )

    return build_asset_file_response(file_path, filename=screenshot.file_name)


@protected_route(
    router.put,
    "/{id}",
    [Scope.ASSETS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def update_screenshot(
    request: Request,
    id: Annotated[int, PathVar(description="Screenshot internal id.", ge=1)],
    is_public: Annotated[bool, Body(embed=True)],
) -> ScreenshotSchema:
    """Toggle a gallery screenshot's public/private visibility (owner only)."""
    screenshot = db_screenshot_handler.get_screenshot_by_id(id)
    if not screenshot or screenshot.user_id != request.user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Screenshot not found",
        )

    updated = db_screenshot_handler.update_screenshot(id, {"is_public": is_public})
    return ScreenshotSchema.model_validate(updated)


@protected_route(
    router.delete,
    "/{id}",
    [Scope.ASSETS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def delete_screenshot(
    request: Request,
    id: Annotated[int, PathVar(description="Screenshot internal id.", ge=1)],
) -> Response:
    """Delete a gallery screenshot — its file and DB row (owner only)."""
    screenshot = db_screenshot_handler.get_screenshot_by_id(id)
    if not screenshot or screenshot.user_id != request.user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Screenshot not found",
        )

    try:
        await fs_asset_handler.remove_file(file_path=screenshot.full_path)
    except FileNotFoundError:
        log.warning(
            f"Screenshot file {hl(screenshot.full_path)} not found on disk; "
            f"removing DB row anyway"
        )

    db_screenshot_handler.delete_screenshot(screenshot.id)
    log.info(f"Deleted screenshot {hl(screenshot.file_name)}")

    return Response()
