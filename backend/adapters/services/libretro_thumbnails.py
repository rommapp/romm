import json
from html.parser import HTMLParser
from urllib.parse import quote, unquote

import aiohttp
import aiohttp.client_exceptions
import yarl
from aiohttp.client import ClientTimeout

from adapters.services.libretro_thumbnails_types import LibretroArtType
from handler.redis_handler import async_cache
from logger.logger import log
from utils import get_version
from utils.context import ctx_aiohttp_session

LIBRETRO_THUMBNAIL_ROOT = "https://thumbnails.libretro.com"
LIBRETRO_LISTING_CACHE_KEY = "romm:libretro:listing"
LIBRETRO_LISTING_CACHE_TTL = 60 * 60 * 24  # 24 hours


class _AnchorHrefParser(HTMLParser):
    """Collects filenames from href attributes of <a> tags in an Apache autoindex page."""

    def __init__(self) -> None:
        super().__init__()
        self.filenames: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for name, value in attrs:
            if name != "href" or not value:
                continue
            # Skip sort/parent/query links exposed by Apache autoindex.
            if value.startswith(("?", "/", "#")) or ".." in value:
                return
            # Only keep image files, since libretro stores PNGs.
            decoded = unquote(value)
            if decoded.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                self.filenames.append(decoded)
            return


class LibretroThumbnailsService:
    """Service to interact with the libretro thumbnail server.

    The server hosts Apache-style directory listings of per-system PNG art at
    https://thumbnails.libretro.com/{System}/{Named_Boxarts|Named_Titles|Named_Logos|Named_Snaps}/
    """

    def __init__(self, base_url: str | None = None) -> None:
        self.url = yarl.URL(base_url or LIBRETRO_THUMBNAIL_ROOT)

    @staticmethod
    def _cache_key(system_name: str, art_type: LibretroArtType) -> str:
        return f"{LIBRETRO_LISTING_CACHE_KEY}:{system_name}:{art_type.value}"

    @staticmethod
    def build_art_url(
        system_name: str, art_type: LibretroArtType, filename: str
    ) -> str:
        subdir = f"{system_name}/{art_type.value}"
        return (
            f"{LIBRETRO_THUMBNAIL_ROOT}/{quote(subdir, safe='/')}"
            f"/{quote(filename, safe='')}"
        )

    async def fetch_listing(
        self, system_name: str, art_type: LibretroArtType
    ) -> list[str]:
        """Return the list of art filenames for a given system + art type.

        Cached in Redis with a 24h TTL to avoid hammering the libretro server.
        """
        cache_key = self._cache_key(system_name, art_type)

        cached = await async_cache.get(cache_key)
        if cached:
            try:
                return json.loads(cached)
            except json.JSONDecodeError:
                log.warning("Invalid cached libretro listing for %s", cache_key)

        subdir = f"{system_name}/{art_type.value}"
        url = f"{self.url}/{quote(subdir, safe='/')}/?F=2"

        aiohttp_session = ctx_aiohttp_session.get()
        try:
            res = await aiohttp_session.get(
                url,
                headers={"user-agent": f"RomM/{get_version()}"},
                timeout=ClientTimeout(total=60),
            )
            res.raise_for_status()
            body = await res.text()
        except aiohttp.client_exceptions.ClientResponseError as exc:
            log.warning(
                "Libretro listing request failed with status %s for URL: %s",
                exc.status,
                url,
            )
            return []
        except aiohttp.client_exceptions.ClientError as exc:
            log.warning("Libretro listing request failed for URL %s: %s", url, exc)
            return []

        parser = _AnchorHrefParser()
        parser.feed(body)
        filenames = parser.filenames

        try:
            await async_cache.set(
                cache_key, json.dumps(filenames), ex=LIBRETRO_LISTING_CACHE_TTL
            )
        except Exception as exc:  # pragma: no cover - cache is best-effort
            log.warning("Failed to cache libretro listing %s: %s", cache_key, exc)

        return filenames

    async def head(self) -> bool:
        """Lightweight connectivity check against the thumbnail server root."""
        aiohttp_session = ctx_aiohttp_session.get()
        try:
            res = await aiohttp_session.head(
                str(self.url),
                headers={"user-agent": f"RomM/{get_version()}"},
                timeout=ClientTimeout(total=10),
                allow_redirects=True,
            )
            return res.status < 500
        except aiohttp.client_exceptions.ClientError:
            return False
