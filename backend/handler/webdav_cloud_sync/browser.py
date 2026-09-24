"""Read-only WebDAV browsing (PROPFIND) of the rom library, for generic WebDAV
clients mounting the Cloud Sync URL. RetroArch itself never browses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
from urllib.parse import quote

from handler.auth.permissions import ResolvedPermissions
from handler.database import db_platform_handler, db_rom_handler
from models.platform import Platform
from models.rom import Rom, apply_file_stats


@dataclass(frozen=True)
class PropfindEntry:
    """One `<D:response>` entry, with an unencoded `href` relative to the mount."""

    href: str
    is_collection: bool
    display_name: str
    content_length: int | None = None
    last_modified: datetime | None = None


@dataclass(frozen=True)
class RomFile:
    """A rom as it appears over WebDAV, as one file even when multi-file."""

    rom_id: int
    display_name: str
    size_bytes: int
    updated_at: datetime


# Clients expect absolute <D:href>s; relative ones make them render the
# requested collection as an endlessly nested subfolder of itself.
WEBDAV_MOUNT_PREFIX = "/api/webdav-cloud-sync"


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
        f"<D:href>{escape(_href_escape(entry.href), quote=False)}</D:href>"
        "<D:propstat><D:prop>"
        f"<D:resourcetype>{resource_type}</D:resourcetype>"
        f"<D:displayname>{escape(entry.display_name, quote=False)}</D:displayname>"
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
    """The name the content endpoint downloads a rom as: a zip when multi-file."""
    if rom.has_multiple_files:
        return f"{rom.fs_name_no_ext}.zip"
    # A nested single file's `fs_name` is its folder; the file has the real name.
    files = sorted(rom.files, key=lambda f: f.file_name)
    return files[0].file_name if files else rom.fs_name


def list_platforms(permissions: ResolvedPermissions) -> list[Platform]:
    platforms = db_platform_handler.get_platforms(
        hidden_platform_ids=list(permissions.hidden_platform_ids)
    )
    return [p for p in platforms if p.rom_count > 0]


def list_rom_files(
    platform: Platform, permissions: ResolvedPermissions
) -> list[RomFile]:
    roms = db_rom_handler.get_roms_scalar(
        platform_ids=[platform.id],
        include_files=True,
        hidden_platform_ids=list(permissions.hidden_platform_ids),
        hidden_rom_ids=list(permissions.hidden_rom_ids),
    )
    rom_files = []
    for rom in roms:
        apply_file_stats(rom, rom.files)
        rom_files.append(
            RomFile(
                rom_id=rom.id,
                display_name=_display_name(rom),
                size_bytes=rom.fs_size_bytes,
                updated_at=rom.updated_at,
            )
        )

    return rom_files


def find_rom_file(
    platform_fs_slug: str, file_name: str, permissions: ResolvedPermissions
) -> RomFile | None:
    platform = db_platform_handler.get_platform_by_fs_slug(platform_fs_slug)
    if not platform:
        return None
    files = list_rom_files(platform, permissions)
    return next((f for f in files if f.display_name == file_name), None)
