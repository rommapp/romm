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
from handler.filesystem import fs_resource_handler
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from utils.router import APIRouter

router = APIRouter()


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

    manuals_path = f"{rom.fs_resources_path}/manual"
    file_location = fs_resource_handler.validate_path(f"{manuals_path}/{rom.id}.pdf")
    log.info(f"Uploading manual to {hl(str(file_location))}")

    await fs_resource_handler.make_directory(manuals_path)

    parser = StreamingFormDataParser(headers=request.headers)
    parser.register("x-upload-platform", NullTarget())
    parser.register(filename, FileTarget(str(file_location)))

    def cleanup_partial_file():
        if file_location.exists():
            file_location.unlink()

    try:
        async for chunk in request.stream():
            parser.data_received(chunk)

        db_rom_handler.update_rom(
            id,
            {
                "path_manual": f"{manuals_path}/{rom.id}.pdf",
            },
        )
    except ClientDisconnect:
        log.error("Client disconnected during upload")
        cleanup_partial_file()
    except Exception as exc:
        log.error("Error uploading files", exc_info=exc)
        cleanup_partial_file()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There was an error uploading the manual",
        ) from exc

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
