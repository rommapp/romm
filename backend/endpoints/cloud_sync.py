"""WebDAV surface for RetroArch's Cloud Sync feature.

Only the verbs RetroArch actually issues are implemented (OPTIONS, GET, PUT,
DELETE, MKCOL, MOVE); there is no PROPFIND because the client diffs a manifest
instead of listing collections. See `handler/cloud_sync_handler.py` for how the
client-side paths map onto RomM's asset storage.

Error responses are deliberately body-less: RetroArch logs failure responses
from a fixed-size buffer, and a large body has been observed to corrupt its
heap.
"""

import os
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse

from handler import cloud_sync_handler, webdav_browser
from handler.auth.constants import Scope
from handler.auth.dependencies import get_permissions
from handler.cloud_sync_handler import MANIFEST_FILE_NAME, AssetKind, CloudSyncPath
from handler.database import db_save_handler, db_state_handler
from handler.filesystem import fs_asset_handler, fs_cloud_sync_blob_handler
from handler.filesystem.assets_handler import build_asset_file_response
from handler.scan_handler import scan_save, scan_state
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.assets import Save, State
from models.rom import Rom
from models.user import User
from utils.filesystem import sanitize_filename

router = APIRouter(prefix="/cloud-sync", tags=["cloud-sync"])

ALLOWED_METHODS = "OPTIONS, PROPFIND, GET, HEAD, PUT, DELETE, MKCOL, MOVE, LOCK, UNLOCK"


def _empty(status_code: int, headers: dict[str, str] | None = None) -> Response:
    return Response(status_code=status_code, headers=headers)


def _unauthorized() -> Response:
    return _empty(
        status.HTTP_401_UNAUTHORIZED,
        {"WWW-Authenticate": 'Basic realm="RomM Cloud Sync"'},
    )


def _authorize(request: Request, scope: Scope) -> Response | None:
    """The response to send instead of handling the request, if any.

    WebDAV clients expect a 401 challenge rather than the 403 that
    `@protected_route` produces, so this endpoint gates itself.
    """
    if not request.user.is_authenticated:
        return _unauthorized()

    if scope not in request.auth.scopes:
        return _empty(status.HTTP_403_FORBIDDEN)

    return None


def _resolve_rom(request: Request, kind: AssetKind, file_name: str) -> Rom | None:
    permissions = get_permissions(request)
    game_name = cloud_sync_handler.game_name_from_file_name(kind, file_name)

    return cloud_sync_handler.resolve_rom(
        game_name,
        lambda rom: permissions.can_see_rom(rom.id, rom.platform_id),
    )


def _get_asset(
    user: User, rom: Rom, parsed: CloudSyncPath, file_name: str
) -> Save | State | None:
    file_path = cloud_sync_handler.build_asset_file_path(
        user, rom, parsed.kind, parsed.emulator
    )

    if parsed.kind == "saves":
        return db_save_handler.get_save_by_path(
            user_id=user.id,
            rom_id=rom.id,
            file_path=file_path,
            file_name=file_name,
        )

    return db_state_handler.get_state_by_path(
        user_id=user.id,
        rom_id=rom.id,
        file_path=file_path,
        file_name=file_name,
    )


@router.api_route("/{file_path:path}", methods=["OPTIONS"], include_in_schema=False)
def cloud_sync_options(request: Request, file_path: str) -> Response:
    """Advertise DAV support. RetroArch stats the base URL before syncing."""
    denied = _authorize(request, Scope.ASSETS_READ)
    if denied:
        return denied

    return _empty(
        status.HTTP_200_OK,
        # Class 2 (locking) is advertised alongside the fake LOCK/UNLOCK
        # below -- some WebDAV clients (iOS Files among them, by report)
        # refuse to treat a server as mountable at all without it, even for
        # read-only browsing.
        {"DAV": "1, 2", "Allow": ALLOWED_METHODS, "MS-Author-Via": "DAV"},
    )


@router.api_route("/{file_path:path}", methods=["LOCK"], include_in_schema=False)
def cloud_sync_lock(request: Request, file_path: str) -> Response:
    """Fake, always-succeeds locking. Nothing here is actually lockable --
    RetroArch's own Cloud Sync client never sends LOCK, and this WebDAV
    surface has no concept of concurrent writers to guard against -- but
    some WebDAV clients (iOS Files among them, by report) won't complete
    "Connect to Server" without a server that at least answers LOCK/UNLOCK,
    so this exists purely for that compatibility handshake."""
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
def cloud_sync_unlock(request: Request, file_path: str) -> Response:
    denied = _authorize(request, Scope.ASSETS_READ)
    if denied:
        return denied

    return _empty(status.HTTP_204_NO_CONTENT)


@router.api_route("/{file_path:path}", methods=["PROPFIND"], include_in_schema=False)
async def cloud_sync_propfind(request: Request, file_path: str) -> Response:
    """Read-only directory browsing for `roms/` (RomM's own library) and
    `saves/`/`states/` (the current cloud-sync manifest), so a real WebDAV
    client (iOS Files' "Connect to Server", Cyberduck, ...) can mount this
    same URL and browse it like a normal file share.

    RetroArch's own Cloud Sync client never issues PROPFIND -- verified
    against its source -- so none of this is on RetroArch's actual sync
    path; it exists solely for read-only human browsing. Unlike the
    retroarch-webdav-romm shim this mirrors, saves/states browsing here
    only shows the manifest's *current* entries, not every historical
    revision -- RomM's own web UI is the place to browse save history.
    """
    denied = _authorize(request, Scope.ASSETS_READ)
    if denied:
        return denied

    depth = 0 if request.headers.get("depth") == "0" else 1
    permissions = get_permissions(request)
    parts = [p for p in file_path.strip("/").split("/") if p]

    entries: list[webdav_browser.PropfindEntry] | None
    if not parts:
        entries = [_root_entry()]
        if depth != 0:
            entries += [
                _roms_root_entry(),
                _virtual_root_entry("saves"),
                _virtual_root_entry("states"),
            ]
    elif parts == ["roms"]:
        entries = [_roms_root_entry()]
        if depth != 0:
            platforms = webdav_browser.list_platforms(permissions.can_see_platform)
            entries += [
                webdav_browser.PropfindEntry(
                    href=f"roms/{p.fs_slug}/", is_collection=True, display_name=p.name
                )
                for p in platforms
            ]
    elif len(parts) == 2 and parts[0] == "roms":
        entries = _platform_listing(parts[1], depth, permissions)
    elif len(parts) == 3 and parts[0] == "roms":
        entries = _rom_file_entry(parts[1], parts[2], permissions)
    elif parts[0] in ("saves", "states"):
        entries = await _save_state_listing(parts, depth, request.user, permissions)
    else:
        entries = None

    if entries is None:
        return _empty(status.HTTP_404_NOT_FOUND)

    body = webdav_browser.build_multistatus(entries)
    return Response(
        content=body,
        status_code=207,
        # iOS Files' WebDAV client is known to be picky about this --
        # "text/xml" (the traditional WebDAV content type) is the safer bet
        # over "application/xml", which some Apple WebDAV client versions
        # have reportedly failed to parse.
        media_type="text/xml; charset=utf-8",
    )


def _root_entry() -> "webdav_browser.PropfindEntry":
    return webdav_browser.PropfindEntry(href="", is_collection=True, display_name="")


def _roms_root_entry() -> "webdav_browser.PropfindEntry":
    return webdav_browser.PropfindEntry(
        href="roms/", is_collection=True, display_name="roms"
    )


def _virtual_root_entry(name: str) -> "webdav_browser.PropfindEntry":
    return webdav_browser.PropfindEntry(
        href=f"{name}/", is_collection=True, display_name=name
    )


def _platform_listing(
    slug: str, depth: int, permissions
) -> list["webdav_browser.PropfindEntry"] | None:
    platforms = webdav_browser.list_platforms(permissions.can_see_platform)
    platform = next((p for p in platforms if p.fs_slug == slug), None)
    if not platform:
        return None

    self_entry = webdav_browser.PropfindEntry(
        href=f"roms/{slug}/", is_collection=True, display_name=platform.name
    )
    if depth == 0:
        return [self_entry]

    files = (
        webdav_browser.list_rom_files(
            slug, lambda rom: permissions.can_see_rom(rom.id, rom.platform_id)
        )
        or []
    )
    return [self_entry] + [
        webdav_browser.PropfindEntry(
            href=f"roms/{slug}/{f.display_name}",
            is_collection=False,
            display_name=f.display_name,
            content_length=f.size_bytes,
            last_modified=f.updated_at,
        )
        for f in files
    ]


def _rom_file_entry(
    slug: str, file_name: str, permissions
) -> list["webdav_browser.PropfindEntry"] | None:
    file = webdav_browser.find_rom_file(
        slug, file_name, lambda rom: permissions.can_see_rom(rom.id, rom.platform_id)
    )
    if not file:
        return None

    return [
        webdav_browser.PropfindEntry(
            href=f"roms/{slug}/{file_name}",
            is_collection=False,
            display_name=file_name,
            content_length=file.size_bytes,
            last_modified=file.updated_at,
        )
    ]


async def _save_state_listing(
    parts: list[str], depth: int, user: User, permissions
) -> list["webdav_browser.PropfindEntry"] | None:
    manifest = await cloud_sync_handler.build_manifest(
        user, lambda rom: permissions.can_see_rom(rom.id, rom.platform_id)
    )
    clean = "/".join(parts)

    exact = next((e for e in manifest if e["path"] == clean), None) if len(parts) > 1 else None
    if exact:
        return [_manifest_file_entry(exact)]

    prefix = f"{clean}/"
    has_children = any(e["path"].startswith(prefix) for e in manifest)
    if len(parts) > 1 and not has_children:
        return None

    self_entry = webdav_browser.PropfindEntry(
        href=prefix, is_collection=True, display_name=parts[-1]
    )
    if depth == 0:
        return [self_entry]

    child_folders: set[str] = set()
    child_files = []
    for entry in manifest:
        if not entry["path"].startswith(prefix):
            continue
        rest = entry["path"][len(prefix) :]
        if "/" in rest:
            child_folders.add(rest.split("/", 1)[0])
        else:
            child_files.append(entry)

    return (
        [self_entry]
        + [
            webdav_browser.PropfindEntry(
                href=f"{prefix}{folder}/", is_collection=True, display_name=folder
            )
            for folder in sorted(child_folders)
        ]
        + [_manifest_file_entry(entry) for entry in child_files]
    )


def _manifest_file_entry(entry: dict[str, str]) -> "webdav_browser.PropfindEntry":
    return webdav_browser.PropfindEntry(
        href=entry["path"],
        is_collection=False,
        display_name=entry["path"].rsplit("/", 1)[-1],
    )


@router.api_route("/{file_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
async def cloud_sync_get(request: Request, file_path: str) -> Response:
    """Serve the manifest, or the bytes of a single save/state."""
    denied = _authorize(request, Scope.ASSETS_READ)
    if denied:
        return denied

    if file_path.strip("/") == MANIFEST_FILE_NAME:
        permissions = get_permissions(request)
        manifest = await cloud_sync_handler.build_manifest(
            request.user,
            lambda rom: permissions.can_see_rom(rom.id, rom.platform_id),
        )
        return JSONResponse(content=manifest)

    blob_path = cloud_sync_handler.parse_cloud_sync_blob_path(file_path)
    if blob_path:
        try:
            resolved_path = fs_cloud_sync_blob_handler.validate_path(
                cloud_sync_handler.user_blob_path(request.user, blob_path)
            )
        except ValueError:
            return _empty(status.HTTP_404_NOT_FOUND)

        if not resolved_path.is_file():
            return _empty(status.HTTP_404_NOT_FOUND)

        return build_asset_file_response(
            resolved_path, filename=os.path.basename(blob_path)
        )

    rom_parts = [p for p in file_path.strip("/").split("/") if p]
    if len(rom_parts) == 3 and rom_parts[0] == "roms":
        permissions = get_permissions(request)
        file = webdav_browser.find_rom_file(
            rom_parts[1],
            rom_parts[2],
            lambda rom: permissions.can_see_rom(rom.id, rom.platform_id),
        )
        if not file:
            return _empty(status.HTTP_404_NOT_FOUND)

        # RomM's own content endpoint already handles Range requests, the
        # multi-file zip cache and (in production) nginx X-Accel-Redirect --
        # duplicating that here would either miss the X-Accel-Redirect step
        # (nothing would actually stream in production) or reimplement it
        # badly. Basic Auth carries over on the redirect, so this stays a
        # single unauthenticated-looking hop from the client's perspective.
        return RedirectResponse(
            url=f"/api/roms/{file.rom_id}/content/{quote(file.display_name)}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    parsed = cloud_sync_handler.parse_cloud_sync_path(file_path)
    if not parsed:
        return _empty(status.HTTP_404_NOT_FOUND)

    rom = _resolve_rom(request, parsed.kind, parsed.file_name)
    if not rom:
        return _empty(status.HTTP_404_NOT_FOUND)

    asset = _get_asset(request.user, rom, parsed, parsed.file_name)
    if not asset:
        return _empty(status.HTTP_404_NOT_FOUND)

    try:
        resolved_path = fs_asset_handler.validate_path(asset.full_path)
    except ValueError:
        return _empty(status.HTTP_404_NOT_FOUND)

    if not resolved_path.is_file():
        return _empty(status.HTTP_404_NOT_FOUND)

    return build_asset_file_response(resolved_path, filename=asset.file_name)


@router.api_route("/{file_path:path}", methods=["PUT"], include_in_schema=False)
async def cloud_sync_put(request: Request, file_path: str) -> Response:
    """Store an uploaded save/state against the ROM its file name points at."""
    denied = _authorize(request, Scope.ASSETS_WRITE)
    if denied:
        return denied

    # The manifest is derived from the database on every read, so the client's
    # copy is accepted and dropped.
    if file_path.strip("/") == MANIFEST_FILE_NAME:
        return _empty(status.HTTP_204_NO_CONTENT)

    # RetroArch also offers config/, thumbnails/ and system/ when those settings
    # are on. None of these belong to a ROM, so they're stored as opaque
    # per-user blobs instead of going through the asset/ROM matching below.
    blob_path = cloud_sync_handler.parse_cloud_sync_blob_path(file_path)
    if blob_path:
        disk_path = cloud_sync_handler.user_blob_path(request.user, blob_path)
        existed = await fs_cloud_sync_blob_handler.file_exists(disk_path)

        await fs_cloud_sync_blob_handler.write_file(
            file=await request.body(),
            path=os.path.dirname(disk_path),
            filename=os.path.basename(disk_path),
        )

        return _empty(
            status.HTTP_204_NO_CONTENT if existed else status.HTTP_201_CREATED
        )

    parsed = cloud_sync_handler.parse_cloud_sync_path(file_path)
    if not parsed:
        return _empty(status.HTTP_409_CONFLICT)

    try:
        file_name = sanitize_filename(parsed.file_name)
    except ValueError:
        return _empty(status.HTTP_409_CONFLICT)

    rom = _resolve_rom(request, parsed.kind, file_name)
    if not rom:
        log.warning(f"Cloud sync upload {hl(file_path)} matches no ROM in the library")
        return _empty(status.HTTP_409_CONFLICT)

    asset_path = cloud_sync_handler.build_asset_file_path(
        request.user, rom, parsed.kind, parsed.emulator
    )

    log.info(f"Cloud sync upload {hl(file_name)} for {hl(str(rom.name), color=BLUE)}")

    await fs_asset_handler.write_file(
        file=await request.body(), path=asset_path, filename=file_name
    )

    existing = _get_asset(request.user, rom, parsed, file_name)

    if parsed.kind == "saves":
        scanned_save = await scan_save(
            file_name=file_name,
            user=request.user,
            platform_fs_slug=rom.platform.fs_slug,
            rom_id=rom.id,
            emulator=parsed.emulator,
        )
        if existing:
            db_save_handler.update_save(
                existing.id,
                {
                    "file_size_bytes": scanned_save.file_size_bytes,
                    "content_hash": scanned_save.content_hash,
                },
            )
        else:
            scanned_save.rom_id = rom.id
            scanned_save.user_id = request.user.id
            scanned_save.emulator = parsed.emulator
            db_save_handler.add_save(save=scanned_save)
    else:
        scanned_state = await scan_state(
            file_name=file_name,
            user=request.user,
            platform_fs_slug=rom.platform.fs_slug,
            rom_id=rom.id,
            emulator=parsed.emulator,
        )
        if existing:
            db_state_handler.update_state(
                existing.id, {"file_size_bytes": scanned_state.file_size_bytes}
            )
        else:
            scanned_state.rom_id = rom.id
            scanned_state.user_id = request.user.id
            scanned_state.emulator = parsed.emulator
            db_state_handler.add_state(state=scanned_state)

    # `last_played` is left alone on purpose: a first sync uploads the whole
    # backlog at once, which would stamp every game as just-played.

    if existing:
        return _empty(status.HTTP_204_NO_CONTENT)

    return _empty(status.HTTP_201_CREATED)


@router.api_route(
    "/{file_path:path}", methods=["DELETE", "MOVE"], include_in_schema=False
)
async def cloud_sync_delete(request: Request, file_path: str) -> Response:
    """Drop a save/state the client no longer has.

    MOVE lands here too. RetroArch uses it in non-destructive mode to shelve the
    file under a `deleted/` prefix; RomM has no such holding area, and keeping
    the row would only make the next sync push the file back to the client.
    """
    denied = _authorize(request, Scope.ASSETS_WRITE)
    if denied:
        return denied

    blob_path = cloud_sync_handler.parse_cloud_sync_blob_path(file_path)
    if blob_path:
        try:
            await fs_cloud_sync_blob_handler.remove_file(
                file_path=cloud_sync_handler.user_blob_path(request.user, blob_path)
            )
        except FileNotFoundError:
            return _empty(status.HTTP_404_NOT_FOUND)

        return _empty(status.HTTP_204_NO_CONTENT)

    parsed = cloud_sync_handler.parse_cloud_sync_path(file_path)
    if not parsed:
        return _empty(status.HTTP_404_NOT_FOUND)

    rom = _resolve_rom(request, parsed.kind, parsed.file_name)
    if not rom:
        return _empty(status.HTTP_404_NOT_FOUND)

    asset = _get_asset(request.user, rom, parsed, parsed.file_name)
    if not asset:
        return _empty(status.HTTP_404_NOT_FOUND)

    log.info(f"Cloud sync delete {hl(asset.file_name)} [{rom.platform_slug}]")

    if parsed.kind == "saves":
        db_save_handler.delete_save(asset.id)
    else:
        db_state_handler.delete_state(asset.id)

    try:
        await fs_asset_handler.remove_file(file_path=asset.full_path)
    except FileNotFoundError:
        pass

    return _empty(status.HTTP_204_NO_CONTENT)


@router.api_route("/{file_path:path}", methods=["MKCOL"], include_in_schema=False)
def cloud_sync_mkcol(request: Request, file_path: str) -> Response:
    """Accept directory creation. Storage layout is derived from the ROM, so
    there is nothing to create; failing here would abort the client's sync."""
    denied = _authorize(request, Scope.ASSETS_WRITE)
    if denied:
        return denied

    return _empty(status.HTTP_201_CREATED)
