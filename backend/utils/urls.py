from __future__ import annotations

import ipaddress
import re
from typing import TYPE_CHECKING, Final
from urllib.parse import parse_qs, quote, urlsplit

import yarl
from fastapi import Request

import config
from utils import valid_youtube_id

if TYPE_CHECKING:
    from models.rom import Rom, RomFile

YOUTUBE_HOSTS: Final = frozenset(
    {"youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com"}
)
YOUTUBE_SHORT_HOSTS: Final = frozenset({"youtu.be", "m.youtu.be"})
YOUTUBE_ID_PATH_PREFIXES: Final = frozenset({"embed", "shorts", "v", "live", "e"})

# The tail of the get_rom_content route, matched whatever host or root path served it.
ROM_CONTENT_PATH_RE: Final = re.compile(r"/api/roms/(\d+)/content/[^/]*$")


def is_shareable_host(host: str) -> bool:
    """Whether a host resolves to something other than the instance itself."""
    if host.lower().rstrip(".") == "localhost":
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True  # A hostname, so assume it resolves for everyone.
    return not address.is_loopback and not address.is_unspecified


def get_public_base_url() -> str | None:
    """Return ROMM_BASE_URL when it points somewhere shareable, else None."""
    try:
        url = yarl.URL(config.ROMM_BASE_URL)
    except ValueError:
        return None
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


def youtube_id_from_url(url: str | None) -> str | None:
    """The video id in a YouTube URL, or None for anything else."""
    url = (url or "").strip()
    if not url:
        return None
    try:
        parts = urlsplit(url)
        # Provider data can omit the scheme.
        if not parts.netloc:
            parts = urlsplit(f"//{url}")
        host = (parts.hostname or "").removeprefix("www.")
    except ValueError:
        return None
    segments = [s for s in parts.path.split("/") if s]
    if host in YOUTUBE_SHORT_HOSTS:
        return valid_youtube_id(segments[0]) if segments else None
    if host not in YOUTUBE_HOSTS:
        return None
    if video_ids := parse_qs(parts.query).get("v"):
        return valid_youtube_id(video_ids[0])
    if len(segments) >= 2 and segments[0] in YOUTUBE_ID_PATH_PREFIXES:
        return valid_youtube_id(segments[1])
    return None
