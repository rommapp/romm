from __future__ import annotations

import ipaddress
import re
from typing import TYPE_CHECKING, Final
from urllib.parse import quote, urlsplit

import yarl
from fastapi import Request

import config

if TYPE_CHECKING:
    from models.rom import Rom, RomFile

# The tail of the get_rom_content route, matched whatever host or root path served it.
ROM_CONTENT_PATH_RE: Final = re.compile(r"/api/roms/(\d+)/content/[^/]*$")


def is_shareable_host(host: str) -> bool:
    """Whether a host resolves to something other than the instance itself."""
    if host.lower() == "localhost":
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True  # A hostname, so assume it resolves for everyone.
    return not address.is_loopback and not address.is_unspecified


def get_public_base_url() -> str | None:
    """Return ROMM_BASE_URL when it points somewhere shareable, else None."""
    url = yarl.URL(config.ROMM_BASE_URL)
    if url.scheme not in ("http", "https") or not url.host:
        return None
    if not is_shareable_host(url.host):
        return None
    return str(url).rstrip("/")


# url_for inserts path params verbatim, so a `#`, `?` or `%` would break the URL.
def rom_content_url(request: Request, rom: Rom) -> str:
    """Absolute download URL for `rom`, its file name percent-encoded."""
    return str(
        request.url_for(
            "get_rom_content", id=rom.id, file_name=quote(rom.fs_name, safe="")
        )
    )


def romfile_content_url(request: Request, file: RomFile) -> str:
    """Absolute download URL for one file of a ROM, its name percent-encoded."""
    return str(
        request.url_for(
            "get_romfile_content",
            file_id=file.id,
            file_name=quote(file.file_name, safe=""),
        )
    )


def rom_id_from_content_url(value: str) -> int | None:
    """The ROM id in a URL `rom_content_url` built, or None for anything else."""
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https"):
        return None
    match = ROM_CONTENT_PATH_RE.search(parts.path)
    return int(match.group(1)) if match else None
