import os
from typing import Annotated

from fastapi import Header, HTTPException
from fastapi import Path as PathVar
from fastapi import Request, status
from fastapi.responses import Response
from starlette.requests import ClientDisconnect
from streaming_form_data import StreamingFormDataParser
from streaming_form_data.targets import FileTarget, NullTarget

from decorators.auth import protected_route
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from handler.auth.constants import Scope
from handler.database import db_rom_handler
from handler.filesystem import fs_rom_handler
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.rom import RomFile, RomFileCategory
from utils.router import APIRouter
from utils.screenshots import (
    ALLOWED_SCREENSHOT_EXTENSIONS,
    is_allowed_screenshot_file,
)

router = APIRouter()

SCREENSHOT_FOLDER = "screenshots"


@protected_route(
    router.post,
    "/{id}/screenshots",
    [Scope.ROMS_WRITE],
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def add_rom_screenshots(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    filename: Annotated[
        str,
        Header(
            description="The name of the file being uploaded.",
            alias="x-upload-filename",
        ),
    ],
) -> Response:
    """Upload a screenshot image for a multi-file ROM."""

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    if rom.has_simple_single_file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Screenshots can only be uploaded to folder-based ROMs",
        )

    try:
        safe_filename = fs_rom_handler._sanitize_filename(filename)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid upload filename: {exc}",
        ) from exc

    # Reject rather than silently strip — otherwise the client's form-field
    # name won't match what we register with the parser below.
    if safe_filename != filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload filename must be a plain file name, not a path",
        )

    if not is_allowed_screenshot_file(safe_filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported image file type. Allowed: "
                f"{', '.join(sorted(ALLOWED_SCREENSHOT_EXTENSIONS))}"
            ),
        )

    screenshot_dir_rel = f"{rom.full_path}/{SCREENSHOT_FOLDER}"
    file_rel_path = f"{screenshot_dir_rel}/{safe_filename}"
    file_location = fs_rom_handler.validate_path(file_rel_path)
    log.info(f"Uploading screenshot to {hl(str(file_location))}")

    await fs_rom_handler.make_directory(screenshot_dir_rel)

    parser = StreamingFormDataParser(headers=request.headers)
    parser.register("x-upload-platform", NullTarget())
    parser.register(safe_filename, FileTarget(str(file_location)))

    def cleanup_partial_file():
        if file_location.exists():
            file_location.unlink()

    try:
        async for chunk in request.stream():
            parser.data_received(chunk)
    except ClientDisconnect:
        log.error("Client disconnected during upload")
        cleanup_partial_file()
        raise
    except Exception as exc:
        log.error("Error uploading screenshot", exc_info=exc)
        cleanup_partial_file()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There was an error uploading the screenshot",
        ) from exc

    stat = os.stat(file_location)
    existing = db_rom_handler.get_rom_file_by_path(
        rom_id=rom.id, file_path=screenshot_dir_rel, file_name=safe_filename
    )
    if existing:
        db_rom_handler.update_rom_file(
            existing.id,
            {
                "file_size_bytes": stat.st_size,
                "last_modified": stat.st_mtime,
                "category": RomFileCategory.SCREENSHOT,
                "missing_from_fs": False,
            },
        )
    else:
        db_rom_handler.add_rom_file(
            RomFile(
                rom_id=rom.id,
                file_name=safe_filename,
                file_path=screenshot_dir_rel,
                file_size_bytes=stat.st_size,
                last_modified=stat.st_mtime,
                category=RomFileCategory.SCREENSHOT,
            )
        )

    return Response(status_code=status.HTTP_201_CREATED)


@protected_route(
    router.delete,
    "/{id}/screenshots/{file_id}",
    [Scope.ROMS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def delete_rom_screenshot(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    file_id: Annotated[int, PathVar(description="Rom file internal id.", ge=1)],
) -> Response:
    """Delete a single screenshot file from a ROM."""

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    rom_file = db_rom_handler.get_rom_file_by_id(file_id)
    if (
        not rom_file
        or rom_file.rom_id != rom.id
        or rom_file.category != RomFileCategory.SCREENSHOT
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Screenshot file not found",
        )

    file_rel_path = rom_file.full_path

    try:
        await fs_rom_handler.remove_file(file_rel_path)
    except FileNotFoundError:
        log.warning(
            f"Screenshot file {hl(file_rel_path)} not found on disk; "
            f"removing DB row anyway"
        )
    except Exception as exc:
        log.error(
            f"Error deleting screenshot {hl(file_rel_path)}",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There was an error deleting the screenshot",
        ) from exc

    db_rom_handler.delete_rom_file(file_id)

    log.info(
        f"Deleted screenshot {hl(rom_file.file_name)} from "
        f"{hl(rom.name or 'ROM', color=BLUE)} [{hl(rom.fs_name)}]"
    )

    return Response()
