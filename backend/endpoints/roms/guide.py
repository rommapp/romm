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
    "/{id}/guides",
    [Scope.ROMS_WRITE],
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def add_rom_guides(
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
    """Upload guides for a rom."""

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    guides_path = f"{rom.fs_resources_path}/guide"
    file_location = fs_resource_handler.validate_path(f"{guides_path}/{rom.id}.pdf")
    log.info(f"Uploading guide to {hl(str(file_location))}")

    await fs_resource_handler.make_directory(guides_path)

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
                "path_guide": f"{guides_path}/{rom.id}.pdf",
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
            detail="There was an error uploading the guide",
        ) from exc

    return Response()


@protected_route(
    router.delete,
    "/{id}/guides",
    [Scope.ROMS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def delete_rom_guides(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
) -> Response:
    """Delete guides for a rom."""

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    if not fs_resource_handler.guide_exists(rom):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No guide found for this ROM",
        )

    try:
        await fs_resource_handler.remove_guide(rom)
        db_rom_handler.update_rom(
            id,
            {
                "path_guide": "",
                "url_guide": "",
            },
        )

        log.info(
            f"Deleted guide for {hl(rom.name or 'ROM', color=BLUE)} [{hl(rom.fs_name)}]"
        )
    except FileNotFoundError:
        log.warning(
            f"Guide file not found for {hl(rom.name or 'ROM', color=BLUE)} [{hl(rom.fs_name)}]"
        )
        # Still update the database even if file doesn't exist
        db_rom_handler.update_rom(
            id,
            {
                "path_guide": "",
                "url_guide": "",
            },
        )
    except Exception as exc:
        log.error(
            f"Error deleting guide for {hl(rom.name or 'ROM', color=BLUE)} [{hl(rom.fs_name)}]",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There was an error deleting the guide",
        ) from exc

    return Response()
