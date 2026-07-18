import os
import re
from typing import Annotated
from urllib.parse import unquote

from fastapi import Body, Header, HTTPException
from fastapi import Path as PathVar
from fastapi import Request, status
from fastapi.responses import Response
from starlette.requests import ClientDisconnect
from streaming_form_data import StreamingFormDataParser
from streaming_form_data.targets import FileTarget, NullTarget

from decorators.auth import protected_route
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from exceptions.fs_exceptions import RomAlreadyExistsException
from handler.auth.constants import Scope
from handler.database import db_rom_handler
from handler.filesystem import fs_rom_handler
from handler.rom_conversion import promote_single_file_to_folder
from handler.walkthrough import fetch_gamefaqs_guide, validate_gamefaqs_url
from handler.walkthrough.gamefaqs import GameFAQsFetchError
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.rom import DocSource, RomFile, RomFileCategory
from utils.media_types import ALLOWED_DOCUMENT_EXTENSIONS
from utils.router import APIRouter

router = APIRouter()

WALKTHROUGH_FOLDER = "walkthrough"

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _is_allowed_walkthrough_file(file_name: str) -> bool:
    _, ext = os.path.splitext(file_name)
    return ext.lower() in ALLOWED_DOCUMENT_EXTENSIONS


def _slugify(value: str, fallback: str = "walkthrough") -> str:
    slug = _SLUG_RE.sub("-", value.lower()).strip("-")
    return (slug[:80] or fallback).strip("-") or fallback


def _decode_header(value: str | None) -> str | None:
    """Percent-decode an optional header value, trimming to the DB column max."""
    if not value:
        return None
    decoded = unquote(value).strip()
    return decoded[:512] or None


@protected_route(
    router.post,
    "/{id}/walkthroughs/files",
    [Scope.ROMS_WRITE],
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_404_NOT_FOUND: {},
        status.HTTP_400_BAD_REQUEST: {},
    },
)
async def add_rom_walkthrough_file(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    filename: Annotated[
        str,
        Header(
            description="The name of the file being uploaded.",
            alias="x-upload-filename",
        ),
    ],
    author: Annotated[
        str | None,
        Header(description="Optional walkthrough author.", alias="x-doc-author"),
    ] = None,
    title: Annotated[
        str | None,
        Header(description="Optional walkthrough title.", alias="x-doc-title"),
    ] = None,
) -> Response:
    """Upload a walkthrough document into the ROM's own walkthrough/ subfolder."""

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    if rom.has_simple_single_file:
        try:
            rom = await promote_single_file_to_folder(rom)
        except RomAlreadyExistsException as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc

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

    if not _is_allowed_walkthrough_file(safe_filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported walkthrough file type. Allowed: "
                f"{', '.join(sorted(ALLOWED_DOCUMENT_EXTENSIONS))}"
            ),
        )

    walkthrough_dir_rel = f"{rom.full_path}/{WALKTHROUGH_FOLDER}"
    file_rel_path = f"{walkthrough_dir_rel}/{safe_filename}"
    file_location = fs_rom_handler.validate_path(file_rel_path)
    log.info(f"Uploading walkthrough file to {hl(str(file_location))}")

    await fs_rom_handler.make_directory(walkthrough_dir_rel)

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
        log.error("Error uploading walkthrough file", exc_info=exc)
        cleanup_partial_file()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There was an error uploading the walkthrough file",
        ) from exc

    stat = os.stat(file_location)
    existing = db_rom_handler.get_rom_file_by_path(
        rom_id=rom.id, file_path=walkthrough_dir_rel, file_name=safe_filename
    )
    if existing:
        db_rom_handler.update_rom_file(
            existing.id,
            {
                "file_size_bytes": stat.st_size,
                "last_modified": stat.st_mtime,
                "category": RomFileCategory.WALKTHROUGH,
                "missing_from_fs": False,
            },
        )
        rom_file_id = existing.id
    else:
        created = db_rom_handler.add_rom_file(
            RomFile(
                rom_id=rom.id,
                file_name=safe_filename,
                file_path=walkthrough_dir_rel,
                file_size_bytes=stat.st_size,
                last_modified=stat.st_mtime,
                category=RomFileCategory.WALKTHROUGH,
            )
        )
        rom_file_id = created.id

    db_rom_handler.upsert_doc_meta(
        rom_file_id=rom_file_id,
        rom_id=rom.id,
        values={
            "source": DocSource.UPLOAD,
            "author": _decode_header(author),
            "title": _decode_header(title),
        },
    )

    return Response(status_code=status.HTTP_201_CREATED)


@protected_route(
    router.post,
    "/{id}/walkthroughs/gamefaqs",
    [Scope.ROMS_WRITE],
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_404_NOT_FOUND: {},
        status.HTTP_400_BAD_REQUEST: {},
        status.HTTP_502_BAD_GATEWAY: {},
    },
)
async def add_rom_gamefaqs_walkthrough(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    body: Annotated[dict, Body()],
) -> Response:
    """Fetch a GameFAQs text guide by URL and store it as a walkthrough.

    The remote page is reduced to plain text on ingest; no HTML is persisted.
    """

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    url = (body.get("url") or "").strip()
    try:
        validate_gamefaqs_url(url)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    try:
        guide = await fetch_gamefaqs_guide(url)
    except GameFAQsFetchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    if rom.has_simple_single_file:
        try:
            rom = await promote_single_file_to_folder(rom)
        except RomAlreadyExistsException as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc

    walkthrough_dir_rel = f"{rom.full_path}/{WALKTHROUGH_FOLDER}"
    base_name = _slugify(guide["title"] or f"gamefaqs-{rom.id}")
    file_name = f"{base_name}.txt"

    # Avoid clobbering an existing walkthrough with the same slug.
    suffix = 1
    while db_rom_handler.get_rom_file_by_path(
        rom_id=rom.id, file_path=walkthrough_dir_rel, file_name=file_name
    ):
        suffix += 1
        file_name = f"{base_name}-{suffix}.txt"

    try:
        await fs_rom_handler.write_file(
            file=guide["text"].encode("utf-8"),
            path=walkthrough_dir_rel,
            filename=file_name,
        )
    except Exception as exc:
        log.error("Error writing GameFAQs walkthrough", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There was an error saving the walkthrough",
        ) from exc

    file_location = fs_rom_handler.validate_path(f"{walkthrough_dir_rel}/{file_name}")
    stat = os.stat(file_location)
    created = db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name=file_name,
            file_path=walkthrough_dir_rel,
            file_size_bytes=stat.st_size,
            last_modified=stat.st_mtime,
            category=RomFileCategory.WALKTHROUGH,
        )
    )
    db_rom_handler.upsert_doc_meta(
        rom_file_id=created.id,
        rom_id=rom.id,
        values={
            "source": DocSource.GAMEFAQS,
            "source_url": url,
            "author": guide["author"],
            "title": guide["title"],
        },
    )

    log.info(
        f"Saved GameFAQs walkthrough {hl(file_name)} for "
        f"{hl(rom.name or 'ROM', color=BLUE)} [{hl(rom.fs_name)}]"
    )

    return Response(status_code=status.HTTP_201_CREATED)


@protected_route(
    router.delete,
    "/{id}/walkthroughs/files/{file_id}",
    [Scope.ROMS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def delete_rom_walkthrough_file(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    file_id: Annotated[int, PathVar(description="Rom file internal id.", ge=1)],
) -> Response:
    """Delete a single walkthrough file from a ROM's walkthrough/ subfolder."""

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    rom_file = db_rom_handler.get_rom_file_by_id(file_id)
    if (
        not rom_file
        or rom_file.rom_id != rom.id
        or rom_file.category != RomFileCategory.WALKTHROUGH
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Walkthrough file not found",
        )

    file_rel_path = rom_file.full_path

    try:
        await fs_rom_handler.remove_file(file_rel_path)
    except FileNotFoundError:
        log.warning(
            f"Walkthrough file {hl(file_rel_path)} not found on disk; "
            f"removing DB row anyway"
        )
    except Exception as exc:
        log.error(f"Error deleting walkthrough file {hl(file_rel_path)}", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There was an error deleting the walkthrough file",
        ) from exc

    # doc_meta and rom_file_user rows cascade on the RomFile delete.
    db_rom_handler.delete_rom_file(file_id)

    log.info(
        f"Deleted walkthrough file {hl(rom_file.file_name)} from "
        f"{hl(rom.name or 'ROM', color=BLUE)} [{hl(rom.fs_name)}]"
    )

    return Response()
