"""Branding (romm-themeable): list theme packs and choose the server's theme."""

import asyncio
import json
import os
import re
from pathlib import Path

from fastapi import HTTPException, Request, status

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
COMPILE_TIMEOUT_SECONDS = 120
STOP_GRACE_SECONDS = 5


class ThemePackSchema(BaseModel):
    id: str
    name: str
    description: str
    author: str
    version: str
    source: str  # "built-in" or "folder"
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


class BrandingSelectionPayload(BaseModel):
    theme: str


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
    for leftover in (
        PACKS_PATH / f"themeable.json.{proc.pid}.tmp",
        RUNTIME_DIR / f"current.{proc.pid}",
    ):
        leftover.unlink(missing_ok=True)


async def _run_compiler(theme: str | None) -> BrandingStatusSchema:
    args = ["node", str(THEMEABLE_HOME / "scripts" / "runtime.mjs")]
    if theme is not None:
        args += ["--select", theme]
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
        result = BrandingStatusSchema.model_validate(json.loads(lines[-1]))
    except (IndexError, ValueError) as exc:
        log.error(
            f"themeable: unreadable compiler output: {stderr.decode(errors='replace')}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The theme compiler returned no status",
        ) from exc
    return result


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
    except (OSError, ValueError):
        return await _run_compiler(None)


@protected_route(router.post, "/branding/rescan", [Scope.ROMS_READ])
async def rescan_branding(request: Request) -> BrandingStatusSchema:
    """Recompile the packs from the themes folder, keeping the saved theme (admin only).

    Args:
        request (Request): FastAPI Request object.

    Returns:
        BrandingStatusSchema: Status after recompiling.
    """
    _require_admin(request)
    return await _run_compiler(None)


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
    result = await _run_compiler(payload.theme)
    log.info(
        f"themeable: {request.user.username} set the server theme to {payload.theme}"
    )
    return result
