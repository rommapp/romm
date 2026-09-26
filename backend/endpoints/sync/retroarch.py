"""WebDAV surface for RetroArch Cloud Sync, plus read-only browsing for generic clients."""

import os
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from tempfile import SpooledTemporaryFile
from urllib.parse import quote

from fastapi import APIRouter, Request, Response, UploadFile, status
from fastapi.responses import JSONResponse, RedirectResponse

from handler.auth.constants import Scope
from handler.auth.dependencies import get_permissions
from handler.auth.permissions import ResolvedPermissions
from handler.database import (
    db_platform_handler,
    db_save_handler,
    db_screenshot_handler,
    db_state_handler,
)
from handler.filesystem import fs_asset_handler, fs_retroarch_sync_handler
from handler.filesystem.assets_handler import build_asset_file_response
from handler.filesystem.base_handler import FSHandler
from handler.scan_handler import scan_save, scan_screenshot, scan_state
from handler.sync.retroarch import browser, psp, sync_handler
from handler.sync.retroarch.device import touch_retroarch_device
from handler.sync.retroarch.sync_handler import (
    MANIFEST_FILE_NAME,
    AssetKind,
    RetroArchSyncPath,
)
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.assets import Save, Screenshot, State
from models.rom import Rom
from models.user import User
from utils.filesystem import sanitize_filename

router = APIRouter(prefix="/retroarch")

ALLOWED_METHODS = "OPTIONS, PROPFIND, GET, HEAD, PUT, DELETE, MKCOL, MOVE, LOCK, UNLOCK"

# Starlette's own threshold for spooling a multipart upload to disk.
_BODY_MEMORY_MAX_BYTES = 1024 * 1024


class _BodyTooLarge(Exception):
    pass


# RetroArch logs failure responses from a fixed-size buffer, and a large body
# has been observed to corrupt its heap.
def _empty(status_code: int, headers: dict[str, str] | None = None) -> Response:
    return Response(status_code=status_code, headers=headers)


def _is_game_library_path(file_path: str, include_root: bool = False) -> bool:
    parts = sync_handler.split_segments(file_path)
    if parts is None:
        return False
    return parts[:1] == ["roms"] or (include_root and not parts)


def _unauthorized() -> Response:
    return _empty(
        status.HTTP_401_UNAUTHORIZED,
        {"WWW-Authenticate": 'Basic realm="RomM Cloud Sync"'},
    )


def _authorize(
    request: Request, scope: Scope, kiosk_allowed: bool = False
) -> Response | None:
    """The 401 challenge or 403 to send instead, which WebDAV clients need over `@protected_route`'s."""
    # RetroArch only sends credentials once challenged, so the anonymous kiosk
    # guest is challenged everywhere outside the game library.
    if not request.user.is_authenticated or (
        request.user.is_kiosk_guest and not kiosk_allowed
    ):
        return _unauthorized()

    if scope not in request.auth.scopes:
        return _empty(status.HTTP_403_FORBIDDEN)

    return None


@asynccontextmanager
async def _request_body(
    request: Request, max_size: int = 0
) -> AsyncIterator[UploadFile]:
    """The request body, spooled to disk past 1 MiB.

    Args:
        max_size: A cap tighter than UploadSizeLimitMiddleware's, if any.

    Raises:
        _BodyTooLarge: The body streamed past `max_size`.
    """
    body = UploadFile(
        SpooledTemporaryFile(max_size=_BODY_MEMORY_MAX_BYTES)  # type: ignore[arg-type]
    )
    try:
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if max_size and size > max_size:
                raise _BodyTooLarge
            await body.write(chunk)

        await body.seek(0)
        yield body
    finally:
        await body.close()


def _can_read_roms(request: Request) -> bool:
    return Scope.ROMS_READ in request.auth.scopes


def _rom_visibility(request: Request) -> Callable[[Rom], bool]:
    permissions = get_permissions(request)
    return lambda rom: permissions.can_see_rom(rom.id, rom.platform_id)


def _resolve_rom(request: Request, kind: AssetKind, file_name: str) -> Rom | None:
    game_name = sync_handler.game_name_from_file_name(kind, file_name)
    return sync_handler.resolve_rom(game_name, _rom_visibility(request))


def _get_asset(
    user: User, rom: Rom, parsed: RetroArchSyncPath
) -> Save | State | Screenshot | None:
    if parsed.is_state_screenshot:
        return sync_handler.resolve_state_screenshot_by_slot(
            user, rom, parsed.emulator, parsed.file_name
        )

    if parsed.kind == "saves":
        file_path = sync_handler.build_asset_file_path(
            user, rom, parsed.kind, parsed.emulator
        )
        return db_save_handler.get_save_by_path(
            user_id=user.id,
            rom_id=rom.id,
            file_path=file_path,
            file_name=parsed.file_name,
        )

    # The requested name is the canonical slot name, which a web-player state's
    # own file name won't match, so the slot is resolved instead.
    return sync_handler.resolve_state_by_slot(
        user, rom, parsed.emulator, parsed.file_name
    )


def _serve(handler: FSHandler, path: str, filename: str) -> Response:
    try:
        resolved_path = handler.validate_path(path)
    except ValueError:
        return _empty(status.HTTP_404_NOT_FOUND)

    if not resolved_path.is_file():
        return _empty(status.HTTP_404_NOT_FOUND)

    return build_asset_file_response(resolved_path, filename=filename)


@router.api_route("/{file_path:path}", methods=["OPTIONS"], include_in_schema=False)
def retroarch_sync_options(request: Request, file_path: str) -> Response:
    """Advertise DAV support. RetroArch stats the base URL before syncing."""
    denied = _authorize(request, Scope.ASSETS_READ)
    if denied:
        return denied

    return _empty(
        status.HTTP_200_OK,
        # Some clients (reportedly iOS Files) won't mount a server without
        # class 2 locking, even read-only.
        {"DAV": "1, 2", "Allow": ALLOWED_METHODS, "MS-Author-Via": "DAV"},
    )


@router.api_route("/{file_path:path}", methods=["LOCK"], include_in_schema=False)
def retroarch_sync_lock(request: Request, file_path: str) -> Response:
    """Always-granted fake lock, for clients that won't mount without one."""
    denied = _authorize(request, Scope.ASSETS_READ)
    if denied:
        return denied

    token = f"opaquelocktoken:{uuid.uuid4()}"
    body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<D:prop xmlns:D="DAV:"><D:lockdiscovery><D:activelock>'
        "<D:locktype><D:write/></D:locktype>"
        "<D:lockscope><D:exclusive/></D:lockscope>"
        "<D:depth>0</D:depth>"
        "<D:timeout>Second-3600</D:timeout>"
        f"<D:locktoken><D:href>{token}</D:href></D:locktoken>"
        "</D:activelock></D:lockdiscovery></D:prop>"
    )
    return Response(
        content=body,
        media_type="text/xml; charset=utf-8",
        headers={"Lock-Token": f"<{token}>"},
    )


@router.api_route("/{file_path:path}", methods=["UNLOCK"], include_in_schema=False)
def retroarch_sync_unlock(request: Request, file_path: str) -> Response:
    denied = _authorize(request, Scope.ASSETS_READ)
    if denied:
        return denied

    return _empty(status.HTTP_204_NO_CONTENT)


@router.api_route("/{file_path:path}", methods=["PROPFIND"], include_in_schema=False)
async def retroarch_sync_propfind(request: Request, file_path: str) -> Response:
    """Read-only browsing of `roms/` and the manifest's `saves/` and `states/`, for generic clients."""
    denied = _authorize(
        request,
        Scope.ASSETS_READ,
        kiosk_allowed=_is_game_library_path(file_path, include_root=True),
    )
    if denied:
        return denied

    depth = 0 if request.headers.get("depth") == "0" else 1
    permissions = get_permissions(request)
    parts = sync_handler.split_segments(file_path)
    if parts is None:
        return _empty(status.HTTP_404_NOT_FOUND)

    if parts and parts[0] == "roms" and not _can_read_roms(request):
        return _empty(status.HTTP_403_FORBIDDEN)

    entries: list[browser.PropfindEntry] | None
    if not parts:
        entries = [_collection_entry("")]
        if depth != 0:
            if _can_read_roms(request):
                entries.append(_collection_entry("roms"))
            if not request.user.is_kiosk_guest:
                entries += [_collection_entry("saves"), _collection_entry("states")]
    elif parts == ["roms"]:
        entries = [_collection_entry("roms")]
        if depth != 0:
            entries += [
                _collection_entry(f"roms/{p.fs_slug}", p.name)
                for p in browser.list_platforms(permissions)
            ]
    elif len(parts) == 2 and parts[0] == "roms":
        entries = _platform_listing(parts[1], depth, permissions)
    elif len(parts) == 3 and parts[0] == "roms":
        entries = _rom_file_entry(parts[1], parts[2], permissions)
    elif parts[0] in ("saves", "states"):
        entries = await _save_state_listing(
            parts, depth, request.user, _rom_visibility(request)
        )
    else:
        entries = None

    if entries is None:
        return _empty(status.HTTP_404_NOT_FOUND)

    body = browser.build_multistatus(entries)
    return Response(
        content=body,
        status_code=207,
        # Some Apple WebDAV clients reportedly fail to parse application/xml.
        media_type="text/xml; charset=utf-8",
    )


def _collection_entry(
    path: str, display_name: str | None = None
) -> browser.PropfindEntry:
    return browser.PropfindEntry(
        href=f"{path}/" if path else "",
        is_collection=True,
        display_name=path.rsplit("/", 1)[-1] if display_name is None else display_name,
    )


def _rom_file_propfind_entry(slug: str, file: browser.RomFile) -> browser.PropfindEntry:
    return browser.PropfindEntry(
        href=f"roms/{slug}/{file.display_name}",
        is_collection=False,
        display_name=file.display_name,
        content_length=file.size_bytes,
        last_modified=file.updated_at,
    )


def _platform_listing(
    slug: str, depth: int, permissions: ResolvedPermissions
) -> list[browser.PropfindEntry] | None:
    platform = db_platform_handler.get_platform_by_fs_slug(slug)
    if (
        not platform
        or platform.rom_count == 0
        or not permissions.can_see_platform(platform.id)
    ):
        return None

    self_entry = _collection_entry(f"roms/{slug}", platform.name)
    if depth == 0:
        return [self_entry]

    return [self_entry] + [
        _rom_file_propfind_entry(slug, file)
        for file in browser.list_rom_files(platform, permissions)
    ]


def _rom_file_entry(
    slug: str, file_name: str, permissions: ResolvedPermissions
) -> list[browser.PropfindEntry] | None:
    file = browser.find_rom_file(slug, file_name, permissions)
    return [_rom_file_propfind_entry(slug, file)] if file else None


async def _save_state_listing(
    parts: list[str], depth: int, user: User, can_see: Callable[[Rom], bool]
) -> list[browser.PropfindEntry] | None:
    tree: AssetKind = "saves" if parts[0] == "saves" else "states"
    paths = await sync_handler.list_manifest_paths(user, can_see, tree)
    clean = "/".join(parts)

    if clean in paths:
        return [_manifest_file_entry(clean)]

    prefix = f"{clean}/"
    has_children = any(path.startswith(prefix) for path in paths)
    if len(parts) > 1 and not has_children:
        return None

    self_entry = _collection_entry(clean)
    if depth == 0:
        return [self_entry]

    child_folders: set[str] = set()
    child_files = []
    for path in paths:
        if not path.startswith(prefix):
            continue
        rest = path[len(prefix) :]
        if "/" in rest:
            child_folders.add(rest.split("/", 1)[0])
        else:
            child_files.append(path)

    return (
        [self_entry]
        + [_collection_entry(f"{clean}/{folder}") for folder in sorted(child_folders)]
        + [_manifest_file_entry(path) for path in child_files]
    )


def _manifest_file_entry(path: str) -> browser.PropfindEntry:
    return browser.PropfindEntry(
        href=path,
        is_collection=False,
        display_name=path.rsplit("/", 1)[-1],
    )


@router.api_route("/{file_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
async def retroarch_sync_get(request: Request, file_path: str) -> Response:
    """Serve the manifest, or the bytes of a single save/state."""
    denied = _authorize(
        request, Scope.ASSETS_READ, kiosk_allowed=_is_game_library_path(file_path)
    )
    if denied:
        return denied

    if file_path.strip("/") == MANIFEST_FILE_NAME:
        touch_retroarch_device(request.user)
        manifest = await sync_handler.build_manifest(
            request.user, _rom_visibility(request)
        )
        return JSONResponse(content=manifest)

    blob_path = sync_handler.parse_retroarch_sync_blob_path(file_path)
    if blob_path:
        return _serve(
            fs_retroarch_sync_handler,
            sync_handler.user_blob_path(request.user, blob_path),
            os.path.basename(blob_path),
        )

    psp_path = psp.resolve_psp_path(file_path)
    if psp_path == "ignore":
        return _empty(status.HTTP_404_NOT_FOUND)
    if psp_path:
        data = await psp.get_psp_file(request.user, psp_path, _rom_visibility(request))
        if data is None:
            return _empty(status.HTTP_404_NOT_FOUND)
        return Response(content=data, media_type="application/octet-stream")

    rom_parts = sync_handler.split_segments(file_path)
    if rom_parts and len(rom_parts) == 3 and rom_parts[0] == "roms":
        if not _can_read_roms(request):
            return _empty(status.HTTP_403_FORBIDDEN)

        file = browser.find_rom_file(
            rom_parts[1], rom_parts[2], get_permissions(request)
        )
        if not file:
            return _empty(status.HTTP_404_NOT_FOUND)

        # The content endpoint already handles Range, the multi-file zip cache
        # and nginx X-Accel-Redirect. Basic Auth carries over on the redirect.
        return RedirectResponse(
            url=f"/api/roms/{file.rom_id}/content/{quote(file.display_name)}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    parsed = sync_handler.parse_retroarch_sync_path(file_path)
    if not parsed:
        return _empty(status.HTTP_404_NOT_FOUND)

    rom = _resolve_rom(request, parsed.kind, parsed.file_name)
    if not rom:
        return _empty(status.HTTP_404_NOT_FOUND)

    asset = _get_asset(request.user, rom, parsed)
    if not asset:
        return _empty(status.HTTP_404_NOT_FOUND)

    return _serve(fs_asset_handler, asset.full_path, asset.file_name)


@router.api_route("/{file_path:path}", methods=["PUT"], include_in_schema=False)
async def retroarch_sync_put(request: Request, file_path: str) -> Response:
    """Store an uploaded save/state against the ROM its file name points at."""
    denied = _authorize(request, Scope.ASSETS_WRITE)
    if denied:
        return denied

    # The manifest is derived from the database on every read, so the client's
    # copy is accepted and dropped.
    if file_path.strip("/") == MANIFEST_FILE_NAME:
        return _empty(status.HTTP_204_NO_CONTENT)

    blob_path = sync_handler.parse_retroarch_sync_blob_path(file_path)
    if blob_path:
        disk_path = sync_handler.user_blob_path(request.user, blob_path)
        async with _request_body(request) as body:
            try:
                existed = await fs_retroarch_sync_handler.file_exists(disk_path)
                await fs_retroarch_sync_handler.write_file(
                    file=body,
                    path=os.path.dirname(disk_path),
                    filename=os.path.basename(disk_path),
                )
            except ValueError:
                return _empty(status.HTTP_409_CONFLICT)

        return _empty(
            status.HTTP_204_NO_CONTENT if existed else status.HTTP_201_CREATED
        )

    psp_path = psp.resolve_psp_path(file_path)
    if psp_path == "ignore":
        # PSP engine cache file (shader cache etc.), not save data.
        return _empty(status.HTTP_204_NO_CONTENT)
    if psp_path:
        # Bundle members are merged in memory, so the bundle limit caps the body.
        try:
            async with _request_body(
                request, psp.BUNDLE_MAX_UNCOMPRESSED_BYTES
            ) as body:
                content = await body.read()
        except _BodyTooLarge:
            return _empty(status.HTTP_413_CONTENT_TOO_LARGE)

        try:
            await psp.put_psp_file(
                request.user, psp_path, content, _rom_visibility(request)
            )
        except psp.PspFolderUnresolved, psp.PspBundleInvalid, ValueError:
            return _empty(status.HTTP_409_CONFLICT)
        return _empty(status.HTTP_201_CREATED)

    parsed = sync_handler.parse_retroarch_sync_path(file_path)
    if not parsed:
        return _empty(status.HTTP_409_CONFLICT)

    # Stored under the client's exact name, or the manifest would advertise a
    # different path than the one the client uploaded.
    file_name = parsed.file_name
    try:
        if sanitize_filename(file_name) != file_name:
            return _empty(status.HTTP_409_CONFLICT)
    except ValueError:
        return _empty(status.HTTP_409_CONFLICT)

    rom = _resolve_rom(request, parsed.kind, file_name)
    if not rom:
        log.warning(f"Cloud sync upload {hl(file_path)} matches no ROM in the library")
        return _empty(status.HTTP_409_CONFLICT)

    log.info(f"Cloud sync upload {hl(file_name)} for {hl(str(rom.name), color=BLUE)}")

    if parsed.is_state_screenshot:
        # Written under the owning state's real name, which may differ from the
        # canonical one, so an existing screenshot is updated rather than forked.
        owning_state = sync_handler.resolve_state_by_slot(
            request.user,
            rom,
            parsed.emulator,
            sync_handler.state_name_of_screenshot(file_name),
        )
        screenshot_file_name = (
            f"{owning_state.file_name}.png" if owning_state else file_name
        )

        screenshot_path = sync_handler.state_screenshot_dir(
            request.user, rom, parsed.emulator
        )
        async with _request_body(request) as body:
            await fs_asset_handler.write_file(
                file=body, path=screenshot_path, filename=screenshot_file_name
            )

        scanned_screenshot = await scan_screenshot(
            file_name=screenshot_file_name,
            user=request.user,
            platform_fs_slug=rom.platform.fs_slug,
            rom_id=rom.id,
            emulator=parsed.emulator,
        )
        existing_screenshot = next(
            (
                shot
                for shot in db_screenshot_handler.get_screenshots(
                    user_id=request.user.id, rom_ids={rom.id}
                )
                if shot.file_name == screenshot_file_name
                and shot.file_path == screenshot_path
            ),
            None,
        )
        if existing_screenshot:
            db_screenshot_handler.update_screenshot(
                existing_screenshot.id,
                {
                    "file_size_bytes": scanned_screenshot.file_size_bytes,
                    "missing_from_fs": False,
                },
            )
            return _empty(status.HTTP_204_NO_CONTENT)

        scanned_screenshot.rom_id = rom.id
        scanned_screenshot.user_id = request.user.id
        db_screenshot_handler.add_screenshot(screenshot=scanned_screenshot)
        return _empty(status.HTTP_201_CREATED)

    asset_path = sync_handler.build_asset_file_path(
        request.user, rom, parsed.kind, parsed.emulator
    )

    # A state resolved by slot may have its own file name; writing to it keeps
    # the row pointing at the fresh bytes instead of orphaning them.
    existing = _get_asset(request.user, rom, parsed)
    write_file_name = existing.file_name if existing else file_name
    replaced_hash = (
        await fs_asset_handler.unrecorded_hash(existing)
        if isinstance(existing, Save)
        else None
    )

    async with _request_body(request) as body:
        await fs_asset_handler.write_file(
            file=body, path=asset_path, filename=write_file_name
        )

    scan = scan_save if parsed.kind == "saves" else scan_state
    scanned = await scan(
        file_name=write_file_name,
        user=request.user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom.id,
        emulator=parsed.emulator,
    )
    if existing:
        # The row moves with the bytes when it was filed elsewhere, e.g. under
        # the ROM's previous platform folder.
        fields = {
            "file_size_bytes": scanned.file_size_bytes,
            "file_path": scanned.file_path,
            "missing_from_fs": False,
        }
        if isinstance(scanned, Save):
            db_save_handler.update_save(
                existing.id,
                {**fields, "content_hash": scanned.content_hash},
                replaced_hash=replaced_hash,
            )
        else:
            db_state_handler.update_state(existing.id, fields)
        if existing.file_path != scanned.file_path:
            with suppress(FileNotFoundError):
                await fs_asset_handler.remove_file(file_path=existing.full_path)
    else:
        scanned.rom_id = rom.id
        scanned.user_id = request.user.id
        scanned.emulator = parsed.emulator
        if isinstance(scanned, Save):
            db_save_handler.add_save(save=scanned)
        else:
            db_state_handler.add_state(state=scanned)

    # `last_played` is left alone on purpose: a first sync uploads the whole
    # backlog at once, which would stamp every game as just-played.
    return _empty(status.HTTP_204_NO_CONTENT if existing else status.HTTP_201_CREATED)


@router.api_route(
    "/{file_path:path}", methods=["DELETE", "MOVE"], include_in_schema=False
)
async def retroarch_sync_delete(request: Request, file_path: str) -> Response:
    """Drop a save/state the client no longer has."""
    # RetroArch's non-destructive mode MOVEs a file under `deleted/`; RomM has no
    # holding area, and keeping the row would push the file back on next sync.
    denied = _authorize(request, Scope.ASSETS_WRITE)
    if denied:
        return denied

    blob_path = sync_handler.parse_retroarch_sync_blob_path(file_path)
    if blob_path:
        try:
            await fs_retroarch_sync_handler.remove_file(
                file_path=sync_handler.user_blob_path(request.user, blob_path)
            )
        except FileNotFoundError:
            return _empty(status.HTTP_404_NOT_FOUND)

        return _empty(status.HTTP_204_NO_CONTENT)

    psp_path = psp.resolve_psp_path(file_path)
    if psp_path:
        if psp_path != "ignore":
            await psp.delete_psp_file(request.user, psp_path, _rom_visibility(request))
        return _empty(status.HTTP_204_NO_CONTENT)

    parsed = sync_handler.parse_retroarch_sync_path(file_path)
    if not parsed:
        return _empty(status.HTTP_404_NOT_FOUND)

    rom = _resolve_rom(request, parsed.kind, parsed.file_name)
    if not rom:
        return _empty(status.HTTP_404_NOT_FOUND)

    asset = _get_asset(request.user, rom, parsed)
    if not asset:
        return _empty(status.HTTP_404_NOT_FOUND)

    log.info(f"Cloud sync delete {hl(asset.file_name)} [{rom.platform_slug}]")

    if isinstance(asset, Screenshot):
        db_screenshot_handler.delete_screenshot(asset.id)
    elif isinstance(asset, Save):
        db_save_handler.delete_save(
            asset.id, content_hash=await fs_asset_handler.unrecorded_hash(asset)
        )
    else:
        db_state_handler.delete_state(asset.id)

    with suppress(FileNotFoundError):
        await fs_asset_handler.remove_file(file_path=asset.full_path)

    return _empty(status.HTTP_204_NO_CONTENT)


@router.api_route("/{file_path:path}", methods=["MKCOL"], include_in_schema=False)
def retroarch_sync_mkcol(request: Request, file_path: str) -> Response:
    """Accept directory creation: the layout is derived, and failing aborts the sync."""
    denied = _authorize(request, Scope.ASSETS_WRITE)
    if denied:
        return denied

    return _empty(status.HTTP_201_CREATED)
