from datetime import datetime, timezone
from typing import Annotated

from anyio import Path
from fastapi import Body, HTTPException
from fastapi import Path as PathVar
from fastapi import Request, status
from fastapi.responses import Response
from starlette.responses import FileResponse

from config import DEV_MODE, DISABLE_DOWNLOAD_ENDPOINT_AUTH
from decorators.auth import protected_route
from endpoints.responses.rom import RomFileSchema, RomFileUserSchema
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from handler.auth.constants import Scope
from handler.auth.dependencies import assert_rom_visible
from handler.database import db_rom_handler
from handler.filesystem import fs_rom_handler
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.rom import DOCUMENT_CATEGORIES, RomFileCategory
from utils.audio_tags import guess_audio_media_type
from utils.media_types import (
    guess_media_file_type,
    is_allowed_document_file,
    is_allowed_media_file,
    is_html_document_file,
)
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

    # Resolve back to the parent rom and enforce its visibility, so a file
    # belonging to a hidden rom can't be read by direct RomFile.id.
    rom = db_rom_handler.get_rom(file.rom_id)
    if not rom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )
    assert_rom_visible(request, rom, not_found_detail="File not found")

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

    # 404-mask file bytes of roms hidden from the caller: resolve the parent
    # rom and apply its visibility before serving any content.
    rom = db_rom_handler.get_rom(file.rom_id)
    if not rom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )
    assert_rom_visible(request, rom, not_found_detail="File not found")

    log.info(
        f"User {hl(current_username, color=BLUE)} is downloading {hl(file.file_name)}"
    )

    # Derive content type / disposition / download name from the trusted DB
    # record, never from the client-supplied file_name path param — otherwise a
    # caller could request the same bytes with an arbitrary extension to force a
    # mismatched Content-Type while served inline (content-sniffing/XSS).
    # Audio, images and videos are served inline so <audio>/<video>/<img> in the
    # details view can render and seek them; everything else downloads.
    if file.category == RomFileCategory.SOUNDTRACK:
        media_type = guess_audio_media_type(file.file_name)
        disposition = "inline"
    elif file.category in DOCUMENT_CATEGORIES and is_allowed_document_file(
        file.file_name
    ):
        # Only document-category files (manuals, walkthroughs) are served inline
        # so the in-page viewer can render them; a game/extra file that happens
        # to end in .pdf/.md/.txt still downloads.
        media_type = guess_media_file_type(file.file_name)
        disposition = "inline"
    elif is_allowed_media_file(file.file_name):
        media_type = guess_media_file_type(file.file_name)
        disposition = "inline"
    else:
        media_type = "application/octet-stream"
        disposition = "attachment"

    # Inline files are served under an explicit, trusted Content-Type; nosniff
    # keeps the browser from sniffing them into anything script-capable (e.g. a
    # Markdown manual into HTML).
    headers = {"X-Content-Type-Options": "nosniff"} if disposition == "inline" else {}
    # HTML documents are sanitized on ingest, but serve them under a sandboxing
    # CSP anyway so a crafted document can never run scripts or reach the
    # session origin if it is opened directly.
    if disposition == "inline" and is_html_document_file(file.file_name):
        headers["Content-Security-Policy"] = "sandbox; default-src 'none'"

    # Serve the file directly in development mode for emulatorjs
    if DEV_MODE:
        rom_path = fs_rom_handler.validate_path(file.full_path)
        # Starlette sets Content-Length and honors Range natively — inline
        # disposition lets <audio> seek via Range requests.
        return FileResponse(
            path=rom_path,
            filename=file.file_name,
            media_type=media_type,
            content_disposition_type=disposition,
            headers=headers,
        )

    # Otherwise proxy through nginx (which parses Range itself via X-Accel-Redirect)
    return FileRedirectResponse(
        download_path=Path(f"/library/{file.full_path}"),
        disposition=disposition,
        media_type=media_type,
        headers=headers,
    )


@protected_route(
    router.delete,
    "/{rom_id}/files/{file_id}",
    [Scope.ROMS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def delete_rom_file(
    request: Request,
    rom_id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    file_id: Annotated[int, PathVar(description="Rom file internal id.", ge=1)],
) -> Response:
    """Delete a single file from a ROM."""

    rom = db_rom_handler.get_rom(rom_id)
    if not rom:
        raise RomNotFoundInDatabaseException(rom_id)

    assert_rom_visible(request, rom, not_found_detail="File not found")

    rom_file = db_rom_handler.get_rom_file_by_id(file_id)
    if not rom_file or rom_file.rom_id != rom.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    file_rel_path = rom_file.full_path

    try:
        await fs_rom_handler.remove_file(file_rel_path)
    except FileNotFoundError:
        log.warning(
            f"ROM file {hl(file_rel_path)} not found on disk; "
            f"removing DB row anyway"
        )
    except Exception as exc:
        log.error(f"Error deleting ROM file {hl(file_rel_path)}", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There was an error deleting the file",
        ) from exc

    db_rom_handler.delete_rom_file(file_id)

    log.info(
        f"Deleted file {hl(rom_file.file_name)} from "
        f"{hl(rom.name or 'ROM', color=BLUE)} [{hl(rom.fs_name)}]"
    )

    return Response()


def _assert_document_file(
    rom_id: int, file_id: int, request: Request
) -> RomFileCategory:
    """Resolve a document-category file, enforcing parent-rom visibility."""
    rom = db_rom_handler.get_rom(rom_id)
    if not rom:
        raise RomNotFoundInDatabaseException(rom_id)
    assert_rom_visible(request, rom, not_found_detail="File not found")

    rom_file = db_rom_handler.get_rom_file_by_id(file_id)
    if (
        not rom_file
        or rom_file.rom_id != rom.id
        or rom_file.category not in DOCUMENT_CATEGORIES
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found",
        )
    return rom_file.category  # type: ignore[return-value]


@protected_route(
    router.get,
    "/{rom_id}/files/{file_id}/progress",
    [Scope.ROMS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def get_rom_file_progress(
    request: Request,
    rom_id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    file_id: Annotated[int, PathVar(description="Rom file internal id.", ge=1)],
) -> RomFileUserSchema:
    """Get the current user's reading progress for a document file."""

    _assert_document_file(rom_id, file_id, request)

    state = db_rom_handler.get_rom_file_user(
        rom_file_id=file_id, user_id=request.user.id
    )
    if state:
        return RomFileUserSchema.model_validate(state)

    # No stored progress yet: return a zeroed default so the client has a shape.
    return RomFileUserSchema(
        rom_file_id=file_id,
        user_id=request.user.id,
        progress=0.0,
        last_page=None,
        finished=False,
        last_read_at=None,
    )


@protected_route(
    router.put,
    "/{rom_id}/files/{file_id}/progress",
    [Scope.ROMS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def update_rom_file_progress(
    request: Request,
    rom_id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    file_id: Annotated[int, PathVar(description="Rom file internal id.", ge=1)],
    body: Annotated[dict, Body()],
) -> RomFileUserSchema:
    """Upsert the current user's reading progress for a document file.

    Reading progress is per-user state (like notes), so only ROMS_READ is
    required, not ROMS_WRITE.
    """

    _assert_document_file(rom_id, file_id, request)

    values: dict = {"last_read_at": datetime.now(timezone.utc)}
    if "progress" in body:
        try:
            values["progress"] = min(1.0, max(0.0, float(body["progress"])))
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="progress must be a number between 0 and 1",
            ) from exc
    if "last_page" in body:
        last_page = body["last_page"]
        if last_page is not None:
            try:
                last_page = max(0, int(last_page))
            except (TypeError, ValueError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="last_page must be an integer",
                ) from exc
        values["last_page"] = last_page
    if "finished" in body:
        values["finished"] = bool(body["finished"])

    state = db_rom_handler.upsert_rom_file_user(
        rom_file_id=file_id, user_id=request.user.id, values=values
    )
    return RomFileUserSchema.model_validate(state)
