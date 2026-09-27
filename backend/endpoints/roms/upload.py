import json
import shutil
from pathlib import Path
from typing import Annotated, Any, cast
from uuid import UUID, uuid4

from anyio import Path as AsyncPath
from anyio import open_file
from fastapi import Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from starlette.requests import ClientDisconnect
from starlette.responses import Response
from streaming_form_data import StreamingFormDataParser
from streaming_form_data.targets import FileTarget, NullTarget

from config import ROM_UPLOAD_TMP_BASE, ROM_UPLOAD_TTL
from decorators.auth import protected_route
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from exceptions.fs_exceptions import RomAlreadyExistsException
from handler.audit_handler import AuditTarget, record
from handler.auth.constants import Scope
from handler.auth.dependencies import assert_rom_visible, get_permissions
from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem import fs_rom_handler
from handler.redis_handler import async_cache
from handler.rom_upload import (
    UploadConflictException,
    UploadDestination,
    UploadNotRegisteredException,
    UploadRejectedException,
    commit_upload,
    parse_upload_folder,
    prepare_upload_destination,
    resolve_upload_destination,
    sanitize_upload_filename,
    staging_path,
)
from logger.logger import log
from models.audit_event import AuditAction
from models.rom import Rom, RomFile
from utils.router import APIRouter

router = APIRouter(
    prefix="/upload",
    tags=["upload"],
)

ROM_ASSEMBLY_CHUNK_SIZE = 8192  # 8KB read buffer during assembly
ROM_UPLOAD_MAX_CHUNK_SIZE = 64 * 1024 * 1024  # 64MB hard cap per chunk


def _session_key(upload_id: str) -> str:
    return f"chunked_upload:{upload_id}"


def _chunks_key(upload_id: str) -> str:
    return f"chunked_upload:{upload_id}:chunks"


def _expected_chunk_size(total_size: int, total_chunks: int, chunk_index: int) -> int:
    """Return expected chunk size using fixed-size chunks with a shorter final chunk."""
    chunk_size = (total_size + total_chunks - 1) // total_chunks
    if chunk_index < total_chunks - 1:
        return chunk_size
    return total_size - (chunk_size * (total_chunks - 1))


async def _get_session(upload_id: str) -> dict[str, Any]:
    raw = await async_cache.get(_session_key(upload_id))
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload session not found or expired",
        )
    return cast(dict[str, Any], json.loads(raw))


async def _save_session(upload_id: str, session: dict[str, Any]) -> None:
    await async_cache.set(
        _session_key(upload_id), json.dumps(session), ex=ROM_UPLOAD_TTL
    )


def _cleanup_tmp(upload_id: str) -> None:
    tmp_dir = ROM_UPLOAD_TMP_BASE / upload_id
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _validate_upload_id(upload_id: str) -> None:
    try:
        UUID(upload_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid upload ID",
        ) from exc


def _validate_session_owner(session: dict[str, Any], user_id: int) -> None:
    if session["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )


async def _cleanup_upload_state(upload_id: str) -> None:
    _cleanup_tmp(upload_id)
    await async_cache.delete(_chunks_key(upload_id))


def _sanitized_filename(filename: str) -> str:
    try:
        return sanitize_upload_filename(filename)
    except UploadRejectedException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


def _get_upload_rom(request: Request, rom_id: int, platform_id: int) -> Rom:
    rom = db_rom_handler.get_rom_simple(rom_id)
    if not rom:
        raise RomNotFoundInDatabaseException(rom_id)
    assert_rom_visible(request, rom)
    if rom.platform_id != platform_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload platform does not match the game's platform",
        )
    return rom


async def _prepare_rom_destination(
    rom: Rom, folder: str, filename: str, *, overwrite: bool
) -> UploadDestination:
    try:
        return await prepare_upload_destination(
            rom, folder, filename, overwrite=overwrite
        )
    except UploadRejectedException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except (UploadConflictException, RomAlreadyExistsException) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


async def _commit(
    destination: UploadDestination, staged: Path, *, overwrite: bool
) -> RomFile | None:
    try:
        return await commit_upload(destination, staged, overwrite=overwrite)
    except UploadConflictException as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except UploadNotRegisteredException as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc


def _upload_target(rom: Rom | None, platform_id: int) -> AuditTarget | None:
    if rom is not None:
        return AuditTarget.of_rom(rom)
    # A platform folder upload has no rom until the next scan finds it.
    platform = db_platform_handler.get_platform(platform_id)
    return AuditTarget.of_platform(platform) if platform else None


def _record_upload(request: Request, rom: Rom | None, session: dict[str, Any]) -> None:
    record(
        AuditAction.ROM_UPLOAD,
        request,
        lambda: _upload_target(rom, session["platform_id"]),
        {
            "file_name": session["filename"],
            "size_bytes": session["total_size"],
            "overwrite": session["overwrite"],
        },
    )


async def receive_rom_file(
    request: Request, rom: Rom, folder: str, filename: str
) -> RomFile | None:
    """Stream a single-file multipart body into a subfolder of the ROM and
    register it the way a chunked upload is, replacing a file of the same name.

    Returns:
        The registered file row, or None when the scanner did not list it.
    """
    safe_filename = _sanitized_filename(filename)
    destination = await _prepare_rom_destination(
        rom, folder, safe_filename, overwrite=True
    )
    staged = staging_path(destination.location)
    log.info(f"Uploading {safe_filename} to {destination.location}")

    parser = StreamingFormDataParser(headers=request.headers)
    parser.register("x-upload-platform", NullTarget())
    parser.register(safe_filename, FileTarget(str(staged)))
    try:
        async for chunk in request.stream():
            parser.data_received(chunk)
    except ClientDisconnect:
        log.error("Client disconnected during upload")
        await AsyncPath(staged).unlink(missing_ok=True)
        raise
    except Exception as exc:
        log.error(f"Error uploading {safe_filename}", exc_info=exc)
        await AsyncPath(staged).unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There was an error uploading the file",
        ) from exc

    # The parser only writes the part whose field name matches the header, so
    # a body naming the file differently leaves nothing behind.
    if not await AsyncPath(staged).exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The upload body has no file part named {safe_filename}",
        )

    return await _commit(destination, staged, overwrite=True)


async def _resolve_destination(
    request: Request, session: dict[str, Any]
) -> UploadDestination:
    """Where a completed upload lands, with its directory created."""
    filename = session["filename"]
    rom_id = session.get("rom_id")
    if rom_id is None:
        try:
            roms_path = fs_rom_handler.get_roms_upload_path(session["platform_fs_slug"])
            location = fs_rom_handler.validate_path(f"{roms_path}/{filename}")
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        await fs_rom_handler.make_directory(roms_path)
        return UploadDestination(rom=None, rel_dir=roms_path, location=location)

    rom = _get_upload_rom(request, rom_id, session["platform_id"])
    return await _prepare_rom_destination(
        rom, session["folder"], filename, overwrite=session["overwrite"]
    )


class UploadTargetPayload(BaseModel):
    """Optional body of `/start`: upload into a ROM's folder instead of the
    platform folder, and name the file where the header cannot."""

    rom_id: int | None = Field(
        default=None,
        ge=1,
        description="Upload into this ROM's folder instead of the platform folder.",
    )
    folder: str = Field(
        default="",
        description="Subfolder inside the ROM's folder, relative and forward-slashed. Empty for the root.",
    )
    filename: str | None = Field(
        default=None,
        description="The file name. Takes precedence over the header, which cannot carry characters outside Latin-1.",
    )
    overwrite: bool = Field(
        default=False,
        description="Replace a file of the same name in the ROM's folder instead of refusing the upload.",
    )


@protected_route(
    router.post,
    "/start",
    [Scope.ROMS_WRITE],
    status_code=status.HTTP_201_CREATED,
)
async def start_chunked_upload(
    request: Request,
    platform_id: Annotated[
        int,
        Header(alias="x-upload-platform", ge=1),
    ],
    filename: Annotated[
        str,
        Header(alias="x-upload-filename"),
    ],
    total_size: Annotated[
        int,
        Header(alias="x-upload-total-size", ge=0),
    ],
    total_chunks: Annotated[
        int,
        Header(alias="x-upload-total-chunks", ge=0),
    ],
    target: UploadTargetPayload | None = None,
) -> dict[str, Any]:
    """Initiate a chunked ROM upload session."""

    # Only an empty file takes no chunks, and it goes straight to /complete.
    if (total_size == 0) != (total_chunks == 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chunk count does not match the file size",
        )

    db_platform = db_platform_handler.get_platform(platform_id)
    # A hidden platform answers like a missing one, so a restricted caller can
    # neither write into its folder nor tell the two apart.
    if not db_platform or not get_permissions(request).can_see_platform(platform_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Platform not found",
        )

    platform_fs_slug = db_platform.fs_slug
    if target and target.filename is not None:
        filename = target.filename
    safe_filename = _sanitized_filename(filename)
    rom_id = target.rom_id if target else None
    overwrite = bool(target and target.overwrite and rom_id is not None)
    rel_folder = ""

    if rom_id is None:
        try:
            roms_path = fs_rom_handler.get_roms_upload_path(platform_fs_slug)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        if await fs_rom_handler.file_exists(f"{roms_path}/{safe_filename}"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File {filename} already exists",
            )
    else:
        rom = _get_upload_rom(request, rom_id, platform_id)
        try:
            rel_folder = parse_upload_folder(target.folder if target else "")
            resolve_upload_destination(
                rom, rel_folder, safe_filename, overwrite=overwrite
            )
        except UploadRejectedException as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        except UploadConflictException as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc

    upload_id = str(uuid4())
    tmp_dir = ROM_UPLOAD_TMP_BASE / upload_id
    tmp_dir.mkdir(parents=True, exist_ok=True)

    session = {
        "upload_id": upload_id,
        "platform_id": platform_id,
        "platform_fs_slug": platform_fs_slug,
        "filename": safe_filename,
        "total_chunks": total_chunks,
        "total_size": total_size,
        "user_id": request.user.id,
        "rom_id": rom_id,
        "folder": rel_folder,
        "overwrite": overwrite,
    }
    await _save_session(upload_id, session)

    log.info(
        f"Started chunked upload session {upload_id} for {safe_filename} "
        f"({total_chunks} chunks, {total_size} bytes)"
    )

    return {"upload_id": upload_id}


@protected_route(
    router.put,
    "/{upload_id}",
    [Scope.ROMS_WRITE],
)
async def upload_chunk(
    request: Request,
    upload_id: str,
    chunk_index: Annotated[
        int,
        Header(alias="x-chunk-index", ge=0),
    ],
) -> dict[str, Any]:
    """Upload a single chunk of a ROM file."""

    _validate_upload_id(upload_id)

    session = await _get_session(upload_id)
    _validate_session_owner(session, request.user.id)

    if chunk_index >= session["total_chunks"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chunk index {chunk_index} out of range (total: {session['total_chunks']})",
        )

    expected_chunk_size = _expected_chunk_size(
        session["total_size"], session["total_chunks"], chunk_index
    )

    if expected_chunk_size > ROM_UPLOAD_MAX_CHUNK_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Chunk size exceeds server maximum",
        )

    if content_length := request.headers.get("content-length"):
        try:
            content_length_bytes = int(content_length)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Content-Length header",
            ) from exc

        if content_length_bytes > ROM_UPLOAD_MAX_CHUNK_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Chunk exceeds maximum allowed size",
            )

    chunk_path = ROM_UPLOAD_TMP_BASE / upload_id / f"{chunk_index:05d}"
    chunk_bytes_written = 0

    try:
        async with await open_file(chunk_path, "wb") as f:
            async for body_chunk in request.stream():
                chunk_bytes_written += len(body_chunk)
                if chunk_bytes_written > ROM_UPLOAD_MAX_CHUNK_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="Chunk exceeds maximum allowed size",
                    )
                await f.write(body_chunk)
    except Exception as exc:
        if chunk_path.exists():
            chunk_path.unlink()
        if isinstance(exc, HTTPException):
            raise
        log.error(
            f"Error writing chunk {chunk_index} for upload {upload_id}", exc_info=exc
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error writing chunk to disk",
        ) from exc

    # Atomically add chunk to set and update TTL
    await async_cache.sadd(_chunks_key(upload_id), chunk_index)
    await async_cache.expire(_chunks_key(upload_id), ROM_UPLOAD_TTL)

    # Get current chunk count
    received_count = await async_cache.scard(_chunks_key(upload_id))

    return {"received": received_count, "total": session["total_chunks"]}


async def _assemble_chunks(
    upload_id: str, session: dict[str, Any], staged: Path
) -> None:
    """Concatenate the received chunks into the staged file, dropping it on
    any failure."""
    total_chunks = session["total_chunks"]
    log.info(f"Assembling {total_chunks} chunks into {staged}")
    assembled_bytes = 0
    try:
        async with await open_file(staged, "wb") as dest:
            for i in range(total_chunks):
                chunk_path = ROM_UPLOAD_TMP_BASE / upload_id / f"{i:05d}"
                async with await open_file(chunk_path, "rb") as src:
                    while True:
                        buf = await src.read(ROM_ASSEMBLY_CHUNK_SIZE)
                        if not buf:
                            break
                        assembled_bytes += len(buf)
                        await dest.write(buf)
        if assembled_bytes != session["total_size"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Assembled file size mismatch: "
                    f"expected {session['total_size']}, got {assembled_bytes}"
                ),
            )
    except Exception as exc:
        await AsyncPath(staged).unlink(missing_ok=True)
        if isinstance(exc, HTTPException):
            raise
        log.error(f"Error assembling upload {upload_id}", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error assembling file chunks",
        ) from exc


@protected_route(
    router.post,
    "/{upload_id}/complete",
    [Scope.ROMS_WRITE],
    status_code=status.HTTP_201_CREATED,
)
async def complete_chunked_upload(
    request: Request,
    upload_id: str,
) -> Response:
    """Assemble all chunks into the final ROM file."""

    _validate_upload_id(upload_id)

    session = await _get_session(upload_id)
    _validate_session_owner(session, request.user.id)

    total_chunks = session["total_chunks"]

    # Atomically get received chunk count and members from Redis set
    received_count = await async_cache.scard(_chunks_key(upload_id))

    if received_count != total_chunks:
        received_chunks_bytes = await async_cache.smembers(_chunks_key(upload_id))
        received_chunks = {int(chunk) for chunk in received_chunks_bytes}
        missing = sorted(set(range(total_chunks)) - received_chunks)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing chunks: {missing}",
        )

    # Atomically claim this upload session so only one /complete can proceed.
    deleted = await async_cache.delete(_session_key(upload_id))
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Upload is already being assembled or has already completed",
        )

    try:
        destination = await _resolve_destination(request, session)
        staged = staging_path(destination.location)
        await _assemble_chunks(upload_id, session, staged)
        await _commit(destination, staged, overwrite=session["overwrite"])
    finally:
        await _cleanup_upload_state(upload_id)

    _record_upload(request, destination.rom, session)
    return Response(status_code=status.HTTP_201_CREATED)


@protected_route(
    router.post,
    "/{upload_id}/cancel",
    [Scope.ROMS_WRITE],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def cancel_chunked_upload(
    request: Request,
    upload_id: str,
) -> Response:
    """Cancel a chunked upload session and clean up temp files."""

    _validate_upload_id(upload_id)

    # Best-effort: session may already be gone because /complete claimed it.
    raw = await async_cache.get(_session_key(upload_id))
    if not raw:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    session = json.loads(raw)
    _validate_session_owner(session, request.user.id)

    await async_cache.delete(_session_key(upload_id))
    await _cleanup_upload_state(upload_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
