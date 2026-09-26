from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import Header, HTTPException
from fastapi import Path as PathVar
from fastapi import Request, status
from fastapi.responses import Response

from decorators.auth import protected_route
from endpoints.responses.rom import (
    CdAudioExtractionSchema,
    CdAudioStatusSchema,
    SoundtrackTrackMetaSchema,
    TrackMetaSchema,
)
from endpoints.roms.upload import receive_rom_file
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from exceptions.fs_exceptions import RomAlreadyExistsException
from handler.auth.constants import Scope
from handler.auth.dependencies import assert_rom_visible
from handler.cd_audio import (
    CdAudioEncodeException,
    CdAudioNeedsFolderException,
    CdAudioUnavailableException,
    cd_audio_status,
    extract_cd_audio,
)
from handler.database import db_rom_handler
from handler.filesystem import fs_rom_handler
from handler.rom_upload import CATEGORY_UPLOAD_FOLDERS, UploadRejectedException
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.rom import RomFileCategory
from utils.audio_tags import remove_persisted_cover
from utils.router import APIRouter

router = APIRouter()


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

    rom = db_rom_handler.get_rom_visibility(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    assert_rom_visible(request, rom)

    tracks = db_rom_handler.get_rom_files_by_category(
        rom_id=rom.id, category=RomFileCategory.SOUNDTRACK
    )

    return [
        SoundtrackTrackMetaSchema(
            file_id=f.id,
            file_name=f.file_name,
            file_size_bytes=f.file_size_bytes,
            track_meta=(
                TrackMetaSchema.model_validate(f.track_meta) if f.track_meta else None
            ),
        )
        for f in tracks
    ]


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
    """Upload a soundtrack audio file into the ROM's soundtrack/ subfolder."""

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    assert_rom_visible(request, rom)

    await receive_rom_file(
        request, rom, CATEGORY_UPLOAD_FOLDERS[RomFileCategory.SOUNDTRACK], filename
    )

    return Response(status_code=status.HTTP_201_CREATED)


@contextmanager
def _cd_audio_errors(rom_id: int, action: str) -> Iterator[None]:
    """Map the CD audio failures both routes share to HTTP errors."""
    try:
        yield
    except CdAudioUnavailableException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except CdAudioEncodeException as exc:
        log.error(f"Failed {action} of ROM {rom_id}", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"There was an error {action}",
        ) from exc


@protected_route(
    router.get,
    "/{id}/soundtracks/cd-audio",
    [Scope.ROMS_READ],
    responses={
        status.HTTP_404_NOT_FOUND: {},
        status.HTTP_503_SERVICE_UNAVAILABLE: {},
    },
)
async def get_rom_cd_audio_status(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
) -> CdAudioStatusSchema:
    """Count the audio tracks on a ROM's disc images and how many are extracted."""

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    assert_rom_visible(request, rom)

    with _cd_audio_errors(id, "reading the disc images"):
        result = await cd_audio_status(rom)

    return CdAudioStatusSchema(tracks=result.tracks, extracted=result.extracted)


@protected_route(
    router.post,
    "/{id}/soundtracks/cd-audio",
    [Scope.ROMS_WRITE],
    responses={
        status.HTTP_400_BAD_REQUEST: {},
        status.HTTP_404_NOT_FOUND: {},
        status.HTTP_409_CONFLICT: {},
        status.HTTP_503_SERVICE_UNAVAILABLE: {},
    },
)
async def extract_rom_cd_audio(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
) -> CdAudioExtractionSchema:
    """Extract the audio tracks of a ROM's disc images into its soundtrack folder."""

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    assert_rom_visible(request, rom)

    try:
        with _cd_audio_errors(id, "extracting the CD audio"):
            result = await extract_cd_audio(rom)
    except UploadRejectedException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except (CdAudioNeedsFolderException, RomAlreadyExistsException) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    return CdAudioExtractionSchema(extracted=result.extracted, skipped=result.skipped)


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

    rom = db_rom_handler.get_rom_visibility_label(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    assert_rom_visible(request, rom)

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

    if rom_file.track_meta and rom_file.track_meta.cover_path:
        remove_persisted_cover(rom_file.track_meta.cover_path)

    db_rom_handler.delete_rom_file(file_id)

    log.info(
        f"Deleted soundtrack {hl(rom_file.file_name)} from "
        f"{hl(rom.name or 'ROM', color=BLUE)} [{hl(rom.fs_name)}]"
    )

    return Response()
