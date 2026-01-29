from pathlib import Path

from fastapi import HTTPException, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field

from decorators.auth import protected_route
from endpoints.responses.rom import WalkthroughSchema
from handler.auth.constants import Scope
from handler.database import db_rom_handler, db_walkthrough_handler
from handler.filesystem import fs_resource_handler
from handler.walkthrough_handler import (
    ALLOWED_MIME_TYPES,
    MAX_UPLOAD_BYTES,
    InvalidWalkthroughURLError,
    WalkthroughContentNotFound,
    WalkthroughError,
    WalkthroughFetchFailed,
    WalkthroughFormat,
    WalkthroughResult,
    WalkthroughSource,
    fetch_walkthrough,
    sanitize_html_fragment,
)
from logger.logger import log
from models.walkthrough import Walkthrough
from utils.router import APIRouter

router = APIRouter(
    prefix="/walkthroughs",
    tags=["walkthroughs"],
)


async def _fetch_walkthrough_with_error_handling(url: str) -> WalkthroughResult:
    """Helper function to fetch walkthrough with consistent error handling."""
    try:
        return await fetch_walkthrough(url)
    except WalkthroughFetchFailed as exc:
        log.error("Walkthrough fetch failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    except InvalidWalkthroughURLError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except WalkthroughContentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except WalkthroughError as exc:
        log.error("Walkthrough fetch failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc


class WalkthroughRequest(BaseModel):
    url: str = Field(..., description="Walkthrough URL from GameFAQs")

    model_config = ConfigDict(use_enum_values=True)


class WalkthroughResponse(BaseModel):
    url: str
    title: str | None = None
    author: str | None = None
    source: WalkthroughSource
    format: WalkthroughFormat
    file_path: str | None = None
    content: str

    model_config = ConfigDict(use_enum_values=True)


class WalkthroughCreateRequest(BaseModel):
    url: str = Field(..., description="Walkthrough URL from GameFAQs")


@protected_route(
    router.post, "/fetch", [Scope.ROMS_READ], status_code=status.HTTP_200_OK
)
async def get_walkthrough(
    request: Request,  # noqa: ARG001 - required for authentication decorator
    payload: WalkthroughRequest,
) -> WalkthroughResponse:
    result = await _fetch_walkthrough_with_error_handling(payload.url)
    return WalkthroughResponse(**result)


def _detect_format_from_extension(filename: str) -> WalkthroughFormat:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return WalkthroughFormat.PDF
    if ext in {".html", ".htm"}:
        return WalkthroughFormat.HTML
    if ext in {".txt", ".text", ".md"}:
        return WalkthroughFormat.TEXT
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported walkthrough file type. Use PDF, HTML, or TXT.",
    )


@protected_route(router.get, "/roms/{rom_id}", [Scope.ROMS_READ])
def list_walkthroughs_for_rom(
    request: Request,  # noqa: ARG001 - required for authentication decorator
    rom_id: int,
) -> list[WalkthroughSchema]:
    rom = db_rom_handler.get_rom(rom_id)
    if not rom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Rom not found"
        )
    walkthroughs = db_walkthrough_handler.get_walkthroughs_for_rom(rom_id)
    return [WalkthroughSchema.model_validate(wt) for wt in walkthroughs]


@protected_route(
    router.post,
    "/roms/{rom_id}",
    [Scope.ROMS_WRITE],
    status_code=status.HTTP_201_CREATED,
)
async def create_walkthrough_for_rom(
    request: Request,  # noqa: ARG001 - required for authentication decorator
    rom_id: int,
    payload: WalkthroughCreateRequest,
) -> WalkthroughSchema:
    rom = db_rom_handler.get_rom(rom_id)
    if not rom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Rom not found"
        )
    result = await _fetch_walkthrough_with_error_handling(payload.url)

    walkthrough = Walkthrough(
        rom_id=rom_id,
        url=payload.url,
        title=result.get("title"),
        author=result.get("author"),
        source=result["source"],
        format=result["format"],
        file_path=None,
        content=result["content"],
    )
    saved = db_walkthrough_handler.add_or_update_walkthrough(walkthrough)
    return WalkthroughSchema.model_validate(saved)


@protected_route(
    router.post,
    "/roms/{rom_id}/upload",
    [Scope.ROMS_WRITE],
    status_code=status.HTTP_201_CREATED,
)
async def upload_walkthrough_for_rom(
    request: Request,  # noqa: ARG001 - required for authentication decorator
    rom_id: int,
    file: UploadFile,
    title: str | None = None,
    author: str | None = None,
) -> WalkthroughSchema:
    rom = db_rom_handler.get_rom(rom_id)
    if not rom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Rom not found"
        )

    filename = file.filename or "walkthrough"
    fmt = _detect_format_from_extension(filename)

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Empty walkthrough file"
        )
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Walkthrough file is too large (max 15MB)",
        )

    if file.content_type:
        content_type = file.content_type.split(";")[0].strip().lower()
        if content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file type. Use PDF, HTML, or TXT.",
            )

    content = ""
    if fmt == WalkthroughFormat.PDF:
        content = ""
    elif fmt == WalkthroughFormat.HTML:
        content = sanitize_html_fragment(
            raw_bytes.decode("utf-8", errors="ignore")
        ).strip()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to parse HTML walkthrough content",
            )
    else:
        content = raw_bytes.decode("utf-8", errors="ignore").strip()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Walkthrough text file is empty",
            )

    walkthrough = Walkthrough(
        rom_id=rom_id,
        url=filename,
        title=title or Path(filename).stem,
        author=author,
        source=WalkthroughSource.UPLOAD,
        format=fmt,
        content=content,
        file_path=None,
    )

    saved = db_walkthrough_handler.add_or_update_walkthrough(walkthrough)

    if fmt == WalkthroughFormat.PDF:
        try:
            stored_path = await fs_resource_handler.store_walkthrough_file(
                rom=rom,
                walkthrough_id=saved.id,
                data=raw_bytes,
                extension="pdf",
            )
            saved.file_path = stored_path
            saved = db_walkthrough_handler.add_or_update_walkthrough(saved)
        except Exception as e:
            log.error(
                f"Failed to store PDF file for walkthrough {saved.id}, rolling back database entry.",
                exc_info=True,
            )
            db_walkthrough_handler.delete_walkthrough(saved.id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store walkthrough file.",
            ) from e

    return WalkthroughSchema.model_validate(saved)


@protected_route(router.delete, "/{walkthrough_id}", [Scope.ROMS_WRITE])
def delete_walkthrough(
    request: Request,  # noqa: ARG001 - required for authentication decorator
    walkthrough_id: int,
) -> dict[str, bool]:
    walkthrough = db_walkthrough_handler.get_walkthrough(walkthrough_id)
    if not walkthrough:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Walkthrough not found"
        )

    if (
        walkthrough.source == WalkthroughSource.UPLOAD
        and walkthrough.file_path is not None
    ):
        fs_resource_handler.remove_walkthrough_file_sync(walkthrough.file_path)

    db_walkthrough_handler.delete_walkthrough(walkthrough_id)
    return {"success": True}
