"""Branding (romm-themeable): list theme packs, choose the server's theme, and upload, rename,
convert and delete packs."""

import asyncio
import json
import os
import re
import uuid
from pathlib import Path

from anyio import Path as AsyncPath
from fastapi import HTTPException, Request, status
from starlette.requests import ClientDisconnect
from streaming_form_data import StreamingFormDataParser
from streaming_form_data.targets import FileTarget

from decorators.auth import protected_route
from endpoints.responses.base import BaseModel
from handler.auth.constants import Scope
from logger.logger import log
from models.user import Role
from utils.router import APIRouter

router = APIRouter(
    prefix="/themeable",
    tags=["themeable"],
)

THEMEABLE_HOME = Path(os.environ.get("THEMEABLE_HOME", "/themeable"))
RUNTIME_DIR = Path(os.environ.get("THEMEABLE_RUNTIME_DIR", "/tmp/themeable"))
PACKS_PATH = Path(os.environ.get("THEMEABLE_PACKS_PATH", "/romm/themes"))
STOCK_THEME = "none"
THEME_ID = re.compile(r"^(none|[a-z0-9][a-z0-9-]{0,63})$")
PACK_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
COMPILE_TIMEOUT_SECONDS = 120
MB = 1024 * 1024
DEFAULT_MAX_UPLOAD_MB = 20


def _max_upload_mb() -> int:
    """THEMEABLE_MAX_UPLOAD_MB, or the default when it is unset or not a positive number."""
    value = os.environ.get("THEMEABLE_MAX_UPLOAD_MB", "")
    return int(value) if value.isdigit() and int(value) > 0 else DEFAULT_MAX_UPLOAD_MB


MAX_UPLOAD_BYTES = _max_upload_mb() * MB
# Room for the multipart boundaries and headers around the file part.
MULTIPART_OVERHEAD_BYTES = 64 * 1024
UPLOAD_FIELD = "file"
STOP_GRACE_SECONDS = 5


class ThemePackSchema(BaseModel):
    id: str
    name: str
    description: str
    author: str
    version: str
    source: str  # "built-in" or "folder"
    format: str = "folder"  # "zip" or "folder"
    swatch: list[str]
    valid: bool
    errors: list[str]
    warnings: list[str]


class ThemeFolderSchema(BaseModel):
    path: str
    exists: bool
    writable: bool
    mounted: bool


class ThemeableClientSchema(BaseModel):
    # Published by themeable/lib/client.mjs, the one home of these values.
    stock_id: str
    follow_server_id: str
    random_id: str
    random_cycle_ms: int
    pack_name_max: int
    guide_url: str
    storage_key: str
    cookie: str
    url_param: str
    preview_param: str
    theme_attribute: str
    stock_swatch: list[str]
    preview: dict[str, str] = {}


class BrandingStatusSchema(BaseModel):
    ok: bool
    generated: str
    selected: str = STOCK_THEME
    effective: str = STOCK_THEME
    notes: list[str] = []
    error: str | None = None
    client: ThemeableClientSchema | None = None
    folder: ThemeFolderSchema | None = None
    packs: list[ThemePackSchema] = []
    hidden: list[str] = []
    max_upload_bytes: int = MAX_UPLOAD_BYTES


class BrandingSelectionPayload(BaseModel):
    theme: str


class PackRenamePayload(BaseModel):
    name: str


def _require_admin(request: Request) -> None:
    if request.user.role != Role.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


async def _stop_compiler(proc: asyncio.subprocess.Process) -> None:
    """Stop a compile that is no longer wanted, wait for it, and clear what it left behind.

    Args:
        proc (asyncio.subprocess.Process): The compiler process.
    """
    if proc.returncode is None:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=STOP_GRACE_SECONDS)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
    # The runtime cleans these up itself unless it was killed mid-run.
    lock = RUNTIME_DIR / "compile.lock"
    try:
        if lock.read_text(encoding="utf-8").strip() == str(proc.pid):
            lock.unlink()
    except OSError:
        pass
    staged_archives = [
        Path(p) async for p in AsyncPath(PACKS_PATH).glob(f".*.{proc.pid}.zip.tmp")
    ]
    for leftover in (
        PACKS_PATH / f"themeable.json.{proc.pid}.tmp",
        RUNTIME_DIR / f"current.{proc.pid}",
        *staged_archives,
    ):
        leftover.unlink(missing_ok=True)


async def _run_runtime(options: list[str]) -> dict:
    args = ["node", str(THEMEABLE_HOME / "scripts" / "runtime.mjs"), *options]
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        log.error(f"themeable: could not run the theme compiler: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The theme compiler could not run",
        ) from exc
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=COMPILE_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError as exc:
        await asyncio.shield(_stop_compiler(proc))
        log.error("themeable: the theme compiler timed out and was stopped")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Compiling the themes took too long and was stopped; nothing was changed",
        ) from exc
    except asyncio.CancelledError:
        await asyncio.shield(_stop_compiler(proc))
        raise

    lines = stdout.decode(errors="replace").strip().splitlines()
    try:
        return json.loads(lines[-1])
    except (IndexError, ValueError) as exc:
        log.error(
            f"themeable: unreadable compiler output: {stderr.decode(errors='replace')}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The theme compiler returned no status",
        ) from exc


async def _run_compiler(options: list[str]) -> BrandingStatusSchema:
    result = await _run_runtime(options)
    try:
        return BrandingStatusSchema.model_validate(result)
    except ValueError as exc:
        log.error(f"themeable: unexpected compiler status: {result}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The theme compiler returned no status",
        ) from exc


def _check_pack_id(pack_id: str) -> None:
    """Refuse ids that aren't packs; RomM default can never be renamed or deleted."""
    if pack_id == STOCK_THEME:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="RomM default can't be renamed or deleted",
        )
    if not PACK_ID.match(pack_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid pack id",
        )


@protected_route(router.get, "/branding", [Scope.ROMS_READ])
async def get_branding(request: Request) -> BrandingStatusSchema:
    """List the installed theme packs and the server's selected theme (admin only).

    Args:
        request (Request): FastAPI Request object.

    Returns:
        BrandingStatusSchema: Packs with their validation status, and the selection.
    """
    _require_admin(request)
    status_file = RUNTIME_DIR / "status.json"
    try:
        return BrandingStatusSchema.model_validate(
            json.loads(status_file.read_text(encoding="utf-8"))
        )
    except OSError, ValueError:
        return await _run_compiler([])


@protected_route(router.post, "/branding/rescan", [Scope.ROMS_READ])
async def rescan_branding(request: Request) -> BrandingStatusSchema:
    """Recompile the packs from the themes folder, keeping the saved theme (admin only).

    Args:
        request (Request): FastAPI Request object.

    Returns:
        BrandingStatusSchema: Status after recompiling.
    """
    _require_admin(request)
    return await _run_compiler([])


@protected_route(router.put, "/branding", [Scope.ROMS_READ])
async def save_branding(
    request: Request, payload: BrandingSelectionPayload
) -> BrandingStatusSchema:
    """Save the server's theme and recompile the packs from the themes folder (admin only).

    Args:
        request (Request): FastAPI Request object.
        payload (BrandingSelectionPayload): Pack id to use, "random" for a pack drawn on
            each page load, or "none" for RomM's default look.

    Returns:
        BrandingStatusSchema: Status after recompiling.
    """
    _require_admin(request)
    if not THEME_ID.match(payload.theme):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid theme id",
        )
    result = await _run_compiler(["--select", payload.theme])
    log.info(
        f"themeable: {request.user.username} set the server theme to {payload.theme}"
    )
    return result


@protected_route(router.post, "/packs/{pack_id}/convert", [Scope.ROMS_READ])
async def convert_pack(request: Request, pack_id: str) -> BrandingStatusSchema:
    """Convert a folder pack in the themes folder to a .zip archive and recompile (admin only).

    Args:
        request (Request): FastAPI Request object.
        pack_id (str): Id of the folder pack to convert.

    Returns:
        BrandingStatusSchema: Status after recompiling; on failure nothing in the folder changes.
    """
    _require_admin(request)
    _check_pack_id(pack_id)
    result = await _run_compiler(["--convert", pack_id])
    if result.ok:
        log.info(f"themeable: {request.user.username} converted {pack_id} to a .zip")
    return result


async def _receive_upload(request: Request, staged: Path) -> None:
    """Stream the multipart file part to `staged`, refusing anything over the size cap."""
    content_length = request.headers.get("content-length")
    if (
        content_length
        and content_length.isdigit()
        and int(content_length) > MAX_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES
    ):
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Theme packs can be at most {MAX_UPLOAD_BYTES // MB} MB",
        )
    try:
        parser = StreamingFormDataParser(headers=request.headers)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Send the pack as a multipart upload",
        ) from exc
    parser.register(UPLOAD_FIELD, FileTarget(str(staged)))
    received = 0
    async for chunk in request.stream():
        received += len(chunk)
        if received > MAX_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Theme packs can be at most {MAX_UPLOAD_BYTES // MB} MB",
            )
        parser.data_received(chunk)
    if not await AsyncPath(staged).exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The upload has no file part named {UPLOAD_FIELD}",
        )
    if (await AsyncPath(staged).stat()).st_size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Theme packs can be at most {MAX_UPLOAD_BYTES // MB} MB",
        )


@protected_route(router.post, "/packs", [Scope.ROMS_READ])
async def upload_pack(request: Request, replace: bool = False) -> BrandingStatusSchema:
    """Upload a .zip theme pack, check it, install it as <id>.zip and recompile (admin only).

    Args:
        request (Request): FastAPI Request object, a multipart body with the archive as `file`.
        replace (bool): Replace a pack with the same id in the themes folder.

    Returns:
        BrandingStatusSchema: Status after recompiling. A pack that fails its checks is
            refused with 422 and its problems, and one whose id is installed with 409 until
            `replace` is set.
    """
    _require_admin(request)
    uploads = RUNTIME_DIR / "uploads"
    await AsyncPath(uploads).mkdir(parents=True, exist_ok=True)
    staged = uploads / f"{uuid.uuid4().hex}.zip"
    try:
        try:
            await _receive_upload(request, staged)
        except ClientDisconnect:
            log.warning("themeable: the client disconnected during a pack upload")
            raise

        report = await _run_runtime(["--validate-archive", str(staged)])
        problems = list(report.get("errors") or [])
        if report.get("existing") == "built-in":
            problems.append(
                f'"{report.get("id")}" is a built-in pack and can\'t be replaced by an upload; give the pack a new id'
            )
        if problems:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"message": "The pack can't be installed", "problems": problems},
            )
        if report.get("existing") == "folder" and not replace:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "A pack with this id is already installed",
                    "id": report.get("id"),
                    "name": report.get("name"),
                },
            )
        result = await _run_compiler(
            ["--install", str(staged), *(["--replace"] if replace else [])]
        )
        if result.ok:
            log.info(
                f"themeable: {request.user.username} uploaded the pack {report.get('id')}"
            )
        return result
    finally:
        await AsyncPath(staged).unlink(missing_ok=True)


@protected_route(router.patch, "/packs/{pack_id}", [Scope.ROMS_READ])
async def rename_pack(
    request: Request, pack_id: str, payload: PackRenamePayload
) -> BrandingStatusSchema:
    """Change an uploaded pack's display name; its id stays the same (admin only).

    Args:
        request (Request): FastAPI Request object.
        pack_id (str): Id of a .zip pack in the themes folder.
        payload (PackRenamePayload): The new display name.

    Returns:
        BrandingStatusSchema: Status after recompiling; on failure the pack is unchanged.
    """
    _require_admin(request)
    _check_pack_id(pack_id)
    result = await _run_compiler(["--rename", pack_id, "--name", payload.name])
    if result.ok:
        log.info(f"themeable: {request.user.username} renamed the pack {pack_id}")
    return result


@protected_route(router.delete, "/packs/{pack_id}", [Scope.ROMS_READ])
async def delete_pack(request: Request, pack_id: str) -> BrandingStatusSchema:
    """Delete an uploaded pack, or hide a built-in one server-wide (admin only).

    Args:
        request (Request): FastAPI Request object.
        pack_id (str): Id of a .zip pack in the themes folder, or of a built-in pack.

    Returns:
        BrandingStatusSchema: Status after recompiling; the server theme falls back to
            RomM default if it was this pack.
    """
    _require_admin(request)
    _check_pack_id(pack_id)
    result = await _run_compiler(["--delete", pack_id])
    if result.ok:
        log.info(f"themeable: {request.user.username} deleted the pack {pack_id}")
    return result


@protected_route(router.post, "/packs/built-ins/restore", [Scope.ROMS_READ])
async def restore_built_in_packs(request: Request) -> BrandingStatusSchema:
    """Show every built-in pack that Delete hid (admin only).

    Args:
        request (Request): FastAPI Request object.

    Returns:
        BrandingStatusSchema: Status after recompiling.
    """
    _require_admin(request)
    return await _run_compiler(["--restore-built-ins"])
