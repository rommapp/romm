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
from endpoints.responses.rom import RomFileAudioMetaSchema, SoundtrackTrackMetaSchema
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from handler.auth.constants import Scope
from handler.database import db_rom_handler
from handler.filesystem import fs_rom_handler
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.rom import RomFile, RomFileCategory
from utils.audio_tags import (
    ALLOWED_AUDIO_EXTENSIONS,
    extract_audio_meta,
    is_allowed_audio_file,
    persist_embedded_cover,
    remove_persisted_cover,
)
from utils.router import APIRouter

router = APIRouter()

SOUNDTRACK_FOLDER = "soundtrack"


@protected_route(
    router.post,
    "/{id}/soundtracks",
    [Scope.ROMS_WRITE],
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def add_rom_soundtracks(
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
    """Upload a soundtrack audio file for a multi-file ROM."""

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    if rom.has_simple_single_file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Soundtracks can only be uploaded to folder-based ROMs",
        )

    try:
        safe_filename = fs_rom_handler._sanitize_filename(filename)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid upload filename: {exc}",
        ) from exc

    # Reject rather than silently strip — otherwise the client's form-field
    # name won't match what we register with the parser below.
    if safe_filename != filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload filename must be a plain file name, not a path",
        )

    if not is_allowed_audio_file(safe_filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported audio file type. Allowed: "
                f"{', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}"
            ),
        )

    soundtrack_dir_rel = f"{rom.full_path}/{SOUNDTRACK_FOLDER}"
    file_rel_path = f"{soundtrack_dir_rel}/{safe_filename}"
    file_location = fs_rom_handler.validate_path(file_rel_path)
    log.info(f"Uploading soundtrack to {hl(str(file_location))}")

    await fs_rom_handler.make_directory(soundtrack_dir_rel)

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
        log.error("Error uploading soundtrack", exc_info=exc)
        cleanup_partial_file()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There was an error uploading the soundtrack",
        ) from exc

    stat = os.stat(file_location)
    audio_meta = extract_audio_meta(str(file_location))
    existing = db_rom_handler.get_rom_file_by_path(
        rom_id=rom.id, file_path=soundtrack_dir_rel, file_name=safe_filename
    )
    if existing:
        # Reuploading: drop stale cover first so a new id-based path can replace it.
        if existing.audio_meta and existing.audio_meta.get("cover_path"):
            remove_persisted_cover(existing.audio_meta["cover_path"])
        saved = db_rom_handler.update_rom_file(
            existing.id,
            {
                "file_size_bytes": stat.st_size,
                "last_modified": stat.st_mtime,
                "category": RomFileCategory.SOUNDTRACK,
                "audio_meta": audio_meta,
                "missing_from_fs": False,
            },
        )
    else:
        saved = db_rom_handler.add_rom_file(
            RomFile(
                rom_id=rom.id,
                file_name=safe_filename,
                file_path=soundtrack_dir_rel,
                file_size_bytes=stat.st_size,
                last_modified=stat.st_mtime,
                category=RomFileCategory.SOUNDTRACK,
                audio_meta=audio_meta,
            )
        )

    if saved and audio_meta and audio_meta.get("has_embedded_cover"):
        cover_path = persist_embedded_cover(
            audio_full_path=str(file_location),
            platform_id=rom.platform_id,
            rom_id=rom.id,
            file_id=saved.id,
        )
        if cover_path:
            persisted_meta = dict(audio_meta)
            persisted_meta["cover_path"] = cover_path
            db_rom_handler.update_rom_file(saved.id, {"audio_meta": persisted_meta})

    return Response()


@protected_route(
    router.delete,
    "/{id}/soundtracks/{file_id}",
    [Scope.ROMS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def delete_rom_soundtrack(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    file_id: Annotated[int, PathVar(description="Rom file internal id.", ge=1)],
) -> Response:
    """Delete a single soundtrack file from a ROM."""

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    rom_file = db_rom_handler.get_rom_file_by_id(file_id)
    if (
        not rom_file
        or rom_file.rom_id != rom.id
        or rom_file.category != RomFileCategory.SOUNDTRACK
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Soundtrack file not found",
        )

    file_rel_path = rom_file.full_path

    try:
        await fs_rom_handler.remove_file(file_rel_path)
    except FileNotFoundError:
        log.warning(
            f"Soundtrack file {hl(file_rel_path)} not found on disk; "
            f"removing DB row anyway"
        )
    except Exception as exc:
        log.error(
            f"Error deleting soundtrack {hl(file_rel_path)}",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There was an error deleting the soundtrack",
        ) from exc

    if rom_file.audio_meta and rom_file.audio_meta.get("cover_path"):
        remove_persisted_cover(rom_file.audio_meta["cover_path"])

    db_rom_handler.delete_rom_file(file_id)

    log.info(
        f"Deleted soundtrack {hl(rom_file.file_name)} from "
        f"{hl(rom.name or 'ROM', color=BLUE)} [{hl(rom.fs_name)}]"
    )

    return Response()


@protected_route(
    router.get,
    "/{id}/soundtracks/metadata",
    [Scope.ROMS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def get_rom_soundtrack_metadata(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
) -> list[SoundtrackTrackMetaSchema]:
    """Return compact audio metadata for every soundtrack file of a ROM."""

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    tracks = db_rom_handler.get_rom_files_by_category(
        rom_id=rom.id, category=RomFileCategory.SOUNDTRACK
    )

    return [
        SoundtrackTrackMetaSchema(
            file_id=f.id,
            file_name=f.file_name,
            file_size_bytes=f.file_size_bytes,
            audio_meta=(
                RomFileAudioMetaSchema.model_validate(f.audio_meta)
                if f.audio_meta
                else None
            ),
        )
        for f in tracks
    ]
