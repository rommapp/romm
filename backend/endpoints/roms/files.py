from typing import Annotated
from urllib.parse import quote

from anyio import Path
from fastapi import HTTPException
from fastapi import Path as PathVar
from fastapi import Request, status
from starlette.responses import FileResponse

from config import DEV_MODE, DISABLE_DOWNLOAD_ENDPOINT_AUTH
from decorators.auth import protected_route
from endpoints.responses.rom import RomFileSchema
from handler.auth.constants import Scope
from handler.database import db_rom_handler
from handler.filesystem import fs_rom_handler
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from utils.nginx import FileRedirectResponse
from utils.router import APIRouter

router = APIRouter()


@protected_route(
    router.get,
    "/{id}/files",
    [Scope.ROMS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def get_romfile(
    request: Request,
    id: Annotated[int, PathVar(description="Rom file internal id.", ge=1)],
) -> RomFileSchema:
    """Retrieve a rom file by ID."""

    file = db_rom_handler.get_rom_file_by_id(id)
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    return RomFileSchema.model_validate(file)


@protected_route(
    router.get,
    "/{id}/files/content/{file_name}",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else [Scope.ROMS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def get_romfile_content(
    request: Request,
    id: Annotated[int, PathVar(description="Rom file internal id.", ge=1)],
    file_name: Annotated[str, PathVar(description="File name to download")],
):
    """Download a rom file."""

    current_username = (
        request.user.username if request.user.is_authenticated else "unknown"
    )

    file = db_rom_handler.get_rom_file_by_id(id)
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    log.info(f"User {hl(current_username, color=BLUE)} is downloading {hl(file_name)}")

    # Serve the file directly in development mode for emulatorjs
    if DEV_MODE:
        rom_path = fs_rom_handler.validate_path(file.full_path)
        return FileResponse(
            path=rom_path,
            filename=file_name,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(file_name)}; filename=\"{quote(file_name)}\"",
                "Content-Type": "application/octet-stream",
                "Content-Length": str(file.file_size_bytes),
            },
        )

    # Otherwise proxy through nginx
    return FileRedirectResponse(
        download_path=Path(f"/library/{file.full_path}"),
    )
