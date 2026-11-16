import ipaddress
from typing import TYPE_CHECKING
from urllib.parse import quote

import yarl
from fastapi import Request

import config

if TYPE_CHECKING:
    from models.rom import Rom


def generate_rom_download_url(request: Request, rom: "Rom") -> str:
    """The ROM's content URL, with its filename encoded as a path segment."""
    return str(
        request.url_for(
            "get_rom_content",
            id=rom.id,
            file_name=quote(rom.fs_name, safe="/"),
        )
    )


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
