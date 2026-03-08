import json
import shutil
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from anyio import open_file
from fastapi import Header, HTTPException, Request, status
from starlette.responses import Response

from decorators.auth import protected_route
from handler.auth.constants import Scope
from handler.database import db_platform_handler
from handler.filesystem import fs_rom_handler
from handler.redis_handler import async_cache
from logger.logger import log
from utils.router import APIRouter

router = APIRouter(
    prefix="/upload",
    tags=["upload"],
)

ROM_UPLOAD_TMP_BASE = Path("/tmp/romm_uploads")
ROM_UPLOAD_TTL = 86400  # 24 hours
ROM_ASSEMBLY_CHUNK_SIZE = 8192  # 8KB read buffer during assembly


def _session_key(upload_id: str) -> str:
    return f"chunked_upload:{upload_id}"


def _chunks_key(upload_id: str) -> str:
    return f"chunked_upload:{upload_id}:chunks"


async def _get_session(upload_id: str) -> dict:
    raw = await async_cache.get(_session_key(upload_id))
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload session not found or expired",
        )
    return json.loads(raw)


async def _save_session(upload_id: str, session: dict) -> None:
    await async_cache.set(
        _session_key(upload_id), json.dumps(session), ex=ROM_UPLOAD_TTL
    )


def _cleanup_tmp(upload_id: str) -> None:
    tmp_dir = ROM_UPLOAD_TMP_BASE / upload_id
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)


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
        Header(alias="x-upload-total-size", ge=1),
    ],
    total_chunks: Annotated[
        int,
        Header(alias="x-upload-total-chunks", ge=1),
    ],
) -> dict:
    """Initiate a chunked ROM upload session."""

    db_platform = db_platform_handler.get_platform(platform_id)
    if not db_platform:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Platform not found",
        )

    platform_fs_slug = db_platform.fs_slug
    roms_path = fs_rom_handler.get_roms_fs_structure(platform_fs_slug)

    if await fs_rom_handler.file_exists(f"{roms_path}/{filename}"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File {filename} already exists",
        )

    upload_id = str(uuid4())
    tmp_dir = ROM_UPLOAD_TMP_BASE / upload_id
    tmp_dir.mkdir(parents=True, exist_ok=True)

    session = {
        "upload_id": upload_id,
        "platform_id": platform_id,
        "platform_fs_slug": platform_fs_slug,
        "filename": filename,
        "total_chunks": total_chunks,
        "total_size": total_size,
        "user_id": request.user.id,
    }
    await _save_session(upload_id, session)

    log.info(
        f"Started chunked upload session {upload_id} for {filename} "
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
) -> dict:
    """Upload a single chunk of a ROM file."""

    # Validate upload_id is a valid UUID to prevent path traversal
    try:
        UUID(upload_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid upload ID",
        ) from exc

    session = await _get_session(upload_id)

    if session["user_id"] != request.user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    if chunk_index >= session["total_chunks"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chunk index {chunk_index} out of range (total: {session['total_chunks']})",
        )

    chunk_path = ROM_UPLOAD_TMP_BASE / upload_id / f"{chunk_index:05d}"

    try:
        chunk_data = await request.body()
        async with await open_file(chunk_path, "wb") as f:
            await f.write(chunk_data)
    except Exception as exc:
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

    try:
        UUID(upload_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid upload ID",
        ) from exc

    session = await _get_session(upload_id)

    if session["user_id"] != request.user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

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

    filename = session["filename"]
    platform_fs_slug = session["platform_fs_slug"]
    roms_path = fs_rom_handler.get_roms_fs_structure(platform_fs_slug)

    try:
        file_location = fs_rom_handler.validate_path(f"{roms_path}/{filename}")
    except ValueError as exc:
        _cleanup_tmp(upload_id)
        await async_cache.delete(_session_key(upload_id))
        await async_cache.delete(_chunks_key(upload_id))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    await fs_rom_handler.make_directory(roms_path)

    log.info(f"Assembling {total_chunks} chunks into {file_location}")

    try:
        async with await open_file(file_location, "wb") as dest:
            for i in range(total_chunks):
                chunk_path = ROM_UPLOAD_TMP_BASE / upload_id / f"{i:05d}"
                async with await open_file(chunk_path, "rb") as src:
                    while True:
                        buf = await src.read(ROM_ASSEMBLY_CHUNK_SIZE)
                        if not buf:
                            break
                        await dest.write(buf)
    except Exception as exc:
        log.error(f"Error assembling upload {upload_id}", exc_info=exc)
        if file_location.exists():
            file_location.unlink()
        _cleanup_tmp(upload_id)
        await async_cache.delete(_session_key(upload_id))
        await async_cache.delete(_chunks_key(upload_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error assembling file chunks",
        ) from exc

    _cleanup_tmp(upload_id)
    await async_cache.delete(_session_key(upload_id))
    await async_cache.delete(_chunks_key(upload_id))

    log.info(f"Chunked upload complete: {file_location}")

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

    try:
        UUID(upload_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid upload ID",
        ) from exc

    # Best-effort: session may already be gone
    raw = await async_cache.get(_session_key(upload_id))
    if raw:
        session = json.loads(raw)
        if session["user_id"] != request.user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden",
            )
        await async_cache.delete(_session_key(upload_id))
        await async_cache.delete(_chunks_key(upload_id))

    _cleanup_tmp(upload_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
