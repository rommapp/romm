from typing import Final, NamedTuple
from urllib.parse import urlparse

import httpx2
from fastapi import status

from adapters.services.screenscraper import media_download_slot
from logger.logger import log
from utils.context import ctx_httpx_client

# Domains (and their subdomains) that metadata providers serve cover art from.
PROVIDER_IMAGE_DOMAINS: Final = frozenset(
    {
        "demozoo.org",
        "igdb.com",
        "launchbox-app.com",
        "mobygames.com",
        "retroachievements.org",
        "screenscraper.fr",
        "steamgriddb.com",
        "steamstatic.com",
        "thegamesdb.net",
        "thumbnails.libretro.com",
        "unstable.life",
    }
)
# Raster only: an SVG served from RomM's origin could run script.
PROVIDER_IMAGE_MEDIA_TYPES: Final = frozenset(
    {
        "image/avif",
        "image/bmp",
        "image/gif",
        "image/jpeg",
        "image/png",
        "image/webp",
    }
)
PROVIDER_IMAGE_MAX_BYTES: Final = 10 * 1024 * 1024
PROVIDER_IMAGE_TIMEOUT_SECONDS: Final = 15


class ProviderImage(NamedTuple):
    content: bytes
    media_type: str


def is_provider_image_url(url: str) -> bool:
    """True only for an https URL on a known provider image domain or subdomain."""
    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError:
        return False

    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        return False
    if port not in (None, 443):
        return False

    return any(
        host == domain or host.endswith(f".{domain}")
        for domain in PROVIDER_IMAGE_DOMAINS
    )


async def fetch_provider_image(url: str) -> ProviderImage | None:
    """Download a provider image, or None when it is missing, too big or not raster."""
    httpx_client = ctx_httpx_client.get()
    try:
        async with media_download_slot(url):
            async with httpx_client.stream(
                "GET",
                url,
                timeout=PROVIDER_IMAGE_TIMEOUT_SECONDS,
                # A redirect could lead off the allowlist.
                follow_redirects=False,
            ) as response:
                if response.status_code != status.HTTP_200_OK:
                    return None

                media_type = (
                    response.headers.get("content-type", "")
                    .split(";", 1)[0]
                    .strip()
                    .lower()
                )
                if media_type not in PROVIDER_IMAGE_MEDIA_TYPES:
                    return None

                declared = response.headers.get("content-length", "")
                if declared.isdigit() and int(declared) > PROVIDER_IMAGE_MAX_BYTES:
                    return None

                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > PROVIDER_IMAGE_MAX_BYTES:
                        return None
    except httpx2.HTTPError as exc:
        log.warning(f"Unable to fetch provider image at {url}: {exc}")
        return None

    return ProviderImage(content=bytes(content), media_type=media_type)
