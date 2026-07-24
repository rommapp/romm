"""Read-only WebDAV browsing (PROPFIND) for RomM's rom library, layered onto
the same `/api/cloud-sync` WebDAV surface RetroArch's Cloud Sync uses.

RetroArch's own Cloud Sync client never issues PROPFIND -- verified against
its source, and already noted in `cloud_sync.py` -- so none of this is on
RetroArch's actual sync path. It exists purely so a real WebDAV client (e.g.
iOS Files app's "Connect to Server", Cyberduck, ...) can mount the same URL
and browse/download the library as plain files, mirroring the
retroarch-webdav-romm shim's `romBrowser.ts` + `webdavXml.ts`.

Read-only by design: there is no PUT/DELETE support for `roms/`, only
GET/HEAD/PROPFIND.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape

from handler.database import db_platform_handler, db_rom_handler
from models.platform import Platform
from models.rom import Rom


@dataclass(frozen=True)
class PropfindEntry:
    """One `<D:response>` entry. `href` is relative to the WebDAV root, e.g.
    `roms/` or `roms/psx/Game.zip` -- never URL-encoded here, that's
    `_href_escape`'s job at render time."""

    href: str
    is_collection: bool
    display_name: str
    content_length: int | None = None
    last_modified: datetime | None = None


@dataclass(frozen=True)
class RomFile:
    """A rom as it appears over WebDAV -- possibly a synthesized zip name
    for a multi-file rom, never the raw per-part file names."""

    rom_id: int
    display_name: str
    size_bytes: int
    updated_at: datetime
    file_ids: list[int] = field(default_factory=list)


# This module's PropfindEntry.href values are relative to the router's own
# mount point (e.g. "roms/", "saves/Snes9x/"), matching the shim's
# `romBrowser.ts`/`webdavXml.ts` -- but WebDAV clients expect every <D:href>
# in a multistatus response to be an absolute path from the *server* root,
# not relative to the collection being PROPFIND'd. Verified live: without
# this prefix, a client (Cyberduck) couldn't match the "self" entry's href
# back to the path it had just requested, and rendered it as an extra,
# never-ending nested subfolder instead of recognizing it as the current
# directory -- the same mismatch made every subfolder look like it
# contained a copy of the whole tree again.
WEBDAV_MOUNT_PREFIX = "/api/cloud-sync"


def _href_escape(path: str) -> str:
    full_path = f"{WEBDAV_MOUNT_PREFIX}/{path}" if path else f"{WEBDAV_MOUNT_PREFIX}/"
    segments = full_path.strip("/").split("/")
    escaped = "/" + "/".join(quote(segment, safe="") for segment in segments)
    return escaped + "/" if full_path.endswith("/") else escaped


def _response_xml(entry: PropfindEntry) -> str:
    resource_type = "<D:collection/>" if entry.is_collection else ""
    extra = (
        ""
        if entry.is_collection
        else (
            f"<D:getcontentlength>{entry.content_length or 0}</D:getcontentlength>"
            "<D:getcontenttype>application/octet-stream</D:getcontenttype>"
        )
    )
    last_modified = (
        f"<D:getlastmodified>{entry.last_modified.strftime('%a, %d %b %Y %H:%M:%S GMT')}</D:getlastmodified>"
        if entry.last_modified
        else ""
    )

    return (
        "<D:response>"
        f"<D:href>{xml_escape(_href_escape(entry.href))}</D:href>"
        "<D:propstat><D:prop>"
        f"<D:resourcetype>{resource_type}</D:resourcetype>"
        f"<D:displayname>{xml_escape(entry.display_name)}</D:displayname>"
        f"{extra}{last_modified}"
        "</D:prop><D:status>HTTP/1.1 200 OK</D:status></D:propstat>"
        "</D:response>"
    )


def build_multistatus(entries: list[PropfindEntry]) -> str:
    body = "".join(_response_xml(entry) for entry in entries)
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<D:multistatus xmlns:D="DAV:">' + body + "</D:multistatus>"
    )


def _display_name(rom: Rom) -> str:
    """RomM zips up genuinely multi-file roms (multi-disc/multi-track games)
    on download and includes an .m3u -- the WebDAV listing should show that
    reality (a .zip) rather than the original fs_name. `has_nested_single_file`
    (one real file sitting a folder deep) still downloads as the raw file, not
    a zip -- only `has_multiple_files` actually triggers zipping server-side.

    For the nested-single-file case, `fs_name` is the *folder* name with no
    extension; the real filename (with extension) is on `files[0].file_name`.
    """
    if rom.has_multiple_files:
        return f"{rom.fs_name_no_ext}.zip"
    files = sorted(rom.files, key=lambda f: f.file_name)
    return files[0].file_name if files else rom.fs_name


def list_platforms(
    can_see_platform: Callable[[int], bool],
) -> list[Platform]:
    platforms = db_platform_handler.get_platforms()
    return [p for p in platforms if p.rom_count > 0 and can_see_platform(p.id)]


def _visible_roms_for_platform(
    platform_fs_slug: str, can_see_rom: Callable[[Rom], bool]
) -> tuple[Platform, list[Rom]] | None:
    platform = db_platform_handler.get_platform_by_fs_slug(platform_fs_slug)
    if not platform:
        return None

    # `get_roms_scalar` doesn't eager-load `files`/`multi_file`/
    # `top_level_file_count` -- filtering visibility only needs `id` and
    # `platform_id`, cheap on the plain query, but `_display_name` below
    # needs those eager-loaded columns, so the visible ids are re-fetched
    # via `get_roms_by_ids` (which does eager-load them) rather than risking
    # a `DetachedInstanceError` on first access outside this session.
    candidate_ids = [
        rom.id
        for rom in db_rom_handler.get_roms_scalar(platform_ids=[platform.id])
        if can_see_rom(rom)
    ]
    roms = db_rom_handler.get_roms_by_ids(candidate_ids)
    return platform, list(roms)


def list_rom_files(
    platform_fs_slug: str, can_see_rom: Callable[[Rom], bool]
) -> list[RomFile] | None:
    """None means the platform itself doesn't exist/isn't visible; an empty
    list means it exists but has nothing the caller can see."""
    resolved = _visible_roms_for_platform(platform_fs_slug, can_see_rom)
    if resolved is None:
        return None

    _platform, roms = resolved
    return [
        RomFile(
            rom_id=rom.id,
            display_name=_display_name(rom),
            size_bytes=rom.fs_size_bytes,
            updated_at=rom.updated_at,
            file_ids=[f.id for f in rom.files],
        )
        for rom in roms
    ]


def find_rom_file(
    platform_fs_slug: str, file_name: str, can_see_rom: Callable[[Rom], bool]
) -> RomFile | None:
    files = list_rom_files(platform_fs_slug, can_see_rom)
    if not files:
        return None
    return next((f for f in files if f.display_name == file_name), None)
