from typing import Annotated

from fastapi import Header, HTTPException
from fastapi import Path as PathVar
from fastapi import Request, status
from fastapi.responses import Response

from decorators.auth import protected_route
from endpoints.roms.upload import receive_rom_file
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from handler.auth.constants import Scope
from handler.auth.dependencies import assert_rom_visible
from handler.database import db_rom_handler
from handler.filesystem import fs_rom_handler
from handler.rom_upload import CATEGORY_UPLOAD_FOLDERS
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.rom import RomFileCategory
from utils.router import APIRouter

router = APIRouter()


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
    """Upload a screenshot image into the ROM's screenshots/ subfolder."""

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    assert_rom_visible(request, rom)

    await receive_rom_file(
        request, rom, CATEGORY_UPLOAD_FOLDERS[RomFileCategory.SCREENSHOT], filename
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

    rom = db_rom_handler.get_rom_visibility_label(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    assert_rom_visible(request, rom)

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
