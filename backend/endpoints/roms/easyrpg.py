from pathlib import Path, PurePosixPath
from typing import Annotated

from fastapi import HTTPException
from fastapi import Path as PathVar
from fastapi import Request, status
from fastapi.responses import JSONResponse, Response
from starlette.responses import FileResponse

from config import DEV_MODE, DISABLE_EASYRPG
from decorators.auth import protected_route
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from handler.auth.constants import Scope
from handler.auth.dependencies import assert_rom_visible, get_permissions
from handler.database import db_rom_handler
from handler.easyrpg import INDEX_FILE, RTP_WEB_PATH, easyrpg_handler
from handler.filesystem import fs_rom_handler
from models.permission import PermAction, PermEntity
from utils.nginx import FileRedirectResponse
from utils.router import APIRouter

router = APIRouter()

# As nginx serves them, so a game's HTML or SVG never renders on this origin.
_OCTET_STREAM = "application/octet-stream"


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _serve(disk_path: str | Path, web_path: PurePosixPath) -> Response:
    if DEV_MODE:
        return FileResponse(path=disk_path, media_type=_OCTET_STREAM)
    return FileRedirectResponse(download_path=web_path)


@protected_route(
    router.get,
    "/{id}/easyrpg/{path:path}",
    [Scope.ROMS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def get_easyrpg_file(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    path: Annotated[str, PathVar(description="File path inside the game folder.")],
) -> Response:
    """Serve a generated `index.json`, or a game or RTP file it names, to the EasyRPG web player."""
    if DISABLE_EASYRPG:
        raise _not_found("EasyRPG is disabled")

    # Only the in-browser player reads these, and a game it runs is the user's own.
    perms = get_permissions(request)
    if not perms.allows(PermEntity.EMULATION, PermAction.READ, owned=True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )

    # The player fetches every asset through here, so the full rom is never loaded.
    rom = db_rom_handler.get_rom_visibility(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    assert_rom_visible(request, rom)

    game_files = easyrpg_handler.game_files(db_rom_handler.present_rom_file_paths(id))
    if not easyrpg_handler.is_game(game_files):
        raise _not_found("Not an RPG Maker 2000/2003 game")

    if path == INDEX_FILE:
        return JSONResponse(
            easyrpg_handler.build_index(game_files),
            headers={"Cache-Control": "no-store"},
        )

    if file := game_files.get(path):
        return _serve(
            fs_rom_handler.validate_path(file.full_path),
            PurePosixPath("/library", file.full_path),
        )

    if rtp_file := easyrpg_handler.find_rtp_file(path):
        return _serve(
            f"{easyrpg_handler.rtp_path}/{rtp_file}",
            PurePosixPath(RTP_WEB_PATH, rtp_file),
        )

    raise _not_found("File not found")
