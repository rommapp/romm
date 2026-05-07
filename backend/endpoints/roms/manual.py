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
from handler.filesystem import fs_resource_handler, fs_rom_handler
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.rom import RomFile, RomFileCategory
from utils.router import APIRouter

router = APIRouter()

MANUAL_FOLDER = "manual"
ALLOWED_MANUAL_EXTENSIONS = frozenset({".pdf"})


def _is_allowed_manual_file(file_name: str) -> bool:
    _, ext = os.path.splitext(file_name)
    return ext.lower() in ALLOWED_MANUAL_EXTENSIONS


@protected_route(
    router.post,
    "/{id}/manuals",
    [Scope.ROMS_WRITE],
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def add_rom_manuals(
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
    """Upload manuals for a rom."""

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    # The stored filename is always `{rom.id}.pdf`; we only use `filename` as
    # the form-field key, but normalise it to a safe basename first.
    try:
        safe_field_name = fs_resource_handler._sanitize_filename(filename)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid upload filename: {exc}",
        ) from exc

    manuals_path = f"{rom.fs_resources_path}/manual"
    file_location = fs_resource_handler.validate_path(f"{manuals_path}/{rom.id}.pdf")
    log.info(f"Uploading manual to {hl(str(file_location))}")

    await fs_resource_handler.make_directory(manuals_path)

    parser = StreamingFormDataParser(headers=request.headers)
    parser.register("x-upload-platform", NullTarget())
    parser.register(safe_field_name, FileTarget(str(file_location)))

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
        log.error("Error uploading files", exc_info=exc)
        cleanup_partial_file()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There was an error uploading the manual",
        ) from exc

    db_rom_handler.update_rom(
        id,
        {
            "path_manual": f"{manuals_path}/{rom.id}.pdf",
        },
    )

    return Response()


@protected_route(
    router.post,
    "/{id}/manuals/redownload",
    [Scope.ROMS_WRITE],
    responses={
        status.HTTP_404_NOT_FOUND: {},
        status.HTTP_400_BAD_REQUEST: {},
    },
)
async def redownload_rom_manual(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
) -> Response:
    """Re-download a rom's manual from its scraped URL (e.g. screenscraper.fr)."""

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    if not rom.url_manual:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No scraped manual URL available for this ROM",
        )

    try:
        path_manual = await fs_resource_handler.get_manual(
            rom=rom,
            overwrite=True,
            url_manual=str(rom.url_manual),
        )
        db_rom_handler.update_rom(id, {"path_manual": path_manual})
        log.info(
            f"Re-downloaded manual for {hl(rom.name or 'ROM', color=BLUE)} "
            f"[{hl(rom.fs_name)}]"
        )
    except Exception as exc:
        log.error("Error re-downloading manual", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There was an error re-downloading the manual",
        ) from exc

    return Response()


@protected_route(
    router.post,
    "/{id}/manuals/files",
    [Scope.ROMS_WRITE],
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_404_NOT_FOUND: {},
        status.HTTP_400_BAD_REQUEST: {},
    },
)
async def add_rom_manual_file(
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
    """Upload a manual PDF into the ROM's own manual/ subfolder."""

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    if rom.has_simple_single_file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Manual files can only be uploaded to folder-based ROMs",
        )

    try:
        safe_filename = fs_rom_handler._sanitize_filename(filename)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid upload filename: {exc}",
        ) from exc

    if safe_filename != filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload filename must be a plain file name, not a path",
        )

    if not _is_allowed_manual_file(safe_filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported manual file type. Allowed: "
                f"{', '.join(sorted(ALLOWED_MANUAL_EXTENSIONS))}"
            ),
        )

    manual_dir_rel = f"{rom.full_path}/{MANUAL_FOLDER}"
    file_rel_path = f"{manual_dir_rel}/{safe_filename}"
    file_location = fs_rom_handler.validate_path(file_rel_path)
    log.info(f"Uploading manual file to {hl(str(file_location))}")

    await fs_rom_handler.make_directory(manual_dir_rel)

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
        log.error("Error uploading manual file", exc_info=exc)
        cleanup_partial_file()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There was an error uploading the manual file",
        ) from exc

    stat = os.stat(file_location)
    existing = db_rom_handler.get_rom_file_by_path(
        rom_id=rom.id, file_path=manual_dir_rel, file_name=safe_filename
    )
    if existing:
        db_rom_handler.update_rom_file(
            existing.id,
            {
                "file_size_bytes": stat.st_size,
                "last_modified": stat.st_mtime,
                "category": RomFileCategory.MANUAL,
                "missing_from_fs": False,
            },
        )
    else:
        db_rom_handler.add_rom_file(
            RomFile(
                rom_id=rom.id,
                file_name=safe_filename,
                file_path=manual_dir_rel,
                file_size_bytes=stat.st_size,
                last_modified=stat.st_mtime,
                category=RomFileCategory.MANUAL,
            )
        )

    return Response()


@protected_route(
    router.delete,
    "/{id}/manuals/files/{file_id}",
    [Scope.ROMS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def delete_rom_manual_file(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    file_id: Annotated[int, PathVar(description="Rom file internal id.", ge=1)],
) -> Response:
    """Delete a single manual file from a ROM's manual/ subfolder."""

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    rom_file = db_rom_handler.get_rom_file_by_id(file_id)
    if (
        not rom_file
        or rom_file.rom_id != rom.id
        or rom_file.category != RomFileCategory.MANUAL
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manual file not found",
        )

    file_rel_path = rom_file.full_path

    try:
        await fs_rom_handler.remove_file(file_rel_path)
    except FileNotFoundError:
        log.warning(
            f"Manual file {hl(file_rel_path)} not found on disk; "
            f"removing DB row anyway"
        )
    except Exception as exc:
        log.error(f"Error deleting manual file {hl(file_rel_path)}", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There was an error deleting the manual file",
        ) from exc

    db_rom_handler.delete_rom_file(file_id)

    log.info(
        f"Deleted manual file {hl(rom_file.file_name)} from "
        f"{hl(rom.name or 'ROM', color=BLUE)} [{hl(rom.fs_name)}]"
    )

    return Response()


@protected_route(
    router.delete,
    "/{id}/manuals",
    [Scope.ROMS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def delete_rom_manuals(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
) -> Response:
    """Delete manuals for a rom."""

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    if not fs_resource_handler.manual_exists(rom):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No manual found for this ROM",
        )

    try:
        await fs_resource_handler.remove_manual(rom)
        db_rom_handler.update_rom(
            id,
            {
                "path_manual": "",
                "url_manual": "",
            },
        )

        log.info(
            f"Deleted manual for {hl(rom.name or 'ROM', color=BLUE)} [{hl(rom.fs_name)}]"
        )
    except FileNotFoundError:
        log.warning(
            f"Manual file not found for {hl(rom.name or 'ROM', color=BLUE)} [{hl(rom.fs_name)}]"
        )
        # Still update the database even if file doesn't exist
        db_rom_handler.update_rom(
            id,
            {
                "path_manual": "",
                "url_manual": "",
            },
        )
    except Exception as exc:
        log.error(
            f"Error deleting manual for {hl(rom.name or 'ROM', color=BLUE)} [{hl(rom.fs_name)}]",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There was an error deleting the manual",
        ) from exc

    return Response()
