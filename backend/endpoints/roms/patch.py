import shutil
import tempfile
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import Body, HTTPException
from fastapi import Path as PathVar
from fastapi import Request, status
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask
from starlette.responses import FileResponse

from decorators.auth import protected_route
from handler.auth.constants import Scope
from handler.database import db_rom_handler
from handler.filesystem import fs_rom_handler
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from utils.rom_patcher import SUPPORTED_PATCH_EXTENSIONS, PatcherError, apply_patch
from utils.router import APIRouter

router = APIRouter()


class PatchRequest(BaseModel):
    patch_file_id: int = Field(description="ID of the patch file (RomFile) to apply.")
    output_file_name: str | None = Field(
        default=None,
        description="Custom output file name. If omitted, derived from ROM + patch names.",
    )


class PatchResponse(BaseModel):
    message: str
    output_file_name: str
    output_file_size: int


@protected_route(
    router.post,
    "/{id}/patch",
    [Scope.ROMS_READ],
    responses={
        status.HTTP_400_BAD_REQUEST: {},
        status.HTTP_404_NOT_FOUND: {},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {},
    },
)
async def patch_rom(
    request: Request,
    id: Annotated[int, PathVar(description="ROM file ID (the base game file).", ge=1)],
    patch_request: PatchRequest = Body(...),
):
    """Apply a patch to a ROM file server-side and return the patched file.

    Both the ROM file and the patch file must already exist in the library.
    The patched ROM is streamed back as a download.
    """

    current_username = (
        request.user.username if request.user.is_authenticated else "unknown"
    )

    rom_file = db_rom_handler.get_rom_file_by_id(id)
    if not rom_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ROM file with id {id} not found",
        )
    if rom_file.missing_from_fs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ROM file '{rom_file.file_name}' is missing from filesystem",
        )

    patch_file = db_rom_handler.get_rom_file_by_id(patch_request.patch_file_id)
    if not patch_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patch file with id {patch_request.patch_file_id} not found",
        )
    if patch_file.missing_from_fs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patch file '{patch_file.file_name}' is missing from filesystem",
        )

    patch_ext = Path(patch_file.file_name).suffix.lower()
    if patch_ext not in SUPPORTED_PATCH_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported patch format '{patch_ext}'. Supported: {', '.join(sorted(SUPPORTED_PATCH_EXTENSIONS))}",
        )

    rom_path = fs_rom_handler.validate_path(rom_file.full_path)
    patch_path = fs_rom_handler.validate_path(patch_file.full_path)

    rom_ext = Path(rom_file.file_name).suffix
    if patch_request.output_file_name:
        output_file_name = f"{Path(patch_request.output_file_name).stem}{rom_ext}"
    else:
        rom_base = Path(rom_file.file_name).stem
        patch_base = Path(patch_file.file_name).stem
        output_file_name = f"{rom_base} (patched-{patch_base}){rom_ext}"

    log.info(
        f"User {hl(current_username, color=BLUE)} is patching "
        f"ROM file {hl(rom_file.file_name)} with patch {hl(patch_file.file_name)}"
    )

    tmp_dir = tempfile.mkdtemp(prefix="romm_patch_")
    output_path = Path(tmp_dir) / output_file_name

    try:
        await apply_patch(rom_path, patch_path, output_path)
    except PatcherError as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        log.error(f"Patching error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected patching error: {e}",
        ) from e

    output_size = output_path.stat().st_size
    log.info(
        f"Successfully patched ROM for user {hl(current_username, color=BLUE)}: "
        f"{hl(output_file_name)} ({output_size} bytes)"
    )

    return FileResponse(
        path=str(output_path),
        filename=output_file_name,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(output_file_name)}; filename=\"{quote(output_file_name)}\"",
            "Content-Length": str(output_size),
        },
        background=BackgroundTask(shutil.rmtree, tmp_dir, True),
    )
