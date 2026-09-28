import asyncio
import http
import json
from typing import Final

import aiohttp
import yarl
from aiohttp.client import ClientTimeout
from fastapi import HTTPException, status

from adapters.services.response_validation import parse_response
from adapters.services.steam_types import (
    SteamAppDetails,
    SteamAppDetailsEnvelope,
    SteamStoreSearchItem,
    SteamStoreSearchResponse,
)
from logger.logger import log
from utils import get_version
from utils.context import ctx_aiohttp_session
from utils.rate_limiter import RateLimiter

# Undocumented, but the storefront starts returning 429 at roughly 200 requests
# per 5 minutes per IP, and a scan spends two requests per game.
STEAM_MAX_REQUESTS_PER_SECOND: Final[float] = 0.6
STEAM_MAX_REQUEST_ATTEMPTS: Final[int] = 3
STEAM_RATE_LIMIT_BACKOFF_SECONDS: Final[float] = 5
_rate_limiter = RateLimiter(STEAM_MAX_REQUESTS_PER_SECOND)

# Undocumented conventions, so an app can have no asset at these URLs.
STEAM_LIBRARY_CAPSULE_URL = (
    "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/"
    "{app_id}/library_600x900.jpg"
)
STEAM_HEADER_IMAGE_URL = (
    "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/"
    "{app_id}/header.jpg"
)


class SteamService:
    """Service to interact with the Steam storefront API.

    Valve documents neither endpoint and promises no compatibility, so every
    failure path degrades to "no result" rather than aborting a scan.
    """

    def __init__(
        self,
        base_url: str | None = None,
    ) -> None:
        self.url = yarl.URL(base_url or "https://store.steampowered.com/api")

    async def _request[T](
        self, url: str, tp: type[T], request_timeout: int = 120
    ) -> T | None:
        aiohttp_session = ctx_aiohttp_session.get()

        for attempt in range(STEAM_MAX_REQUEST_ATTEMPTS):
            await _rate_limiter.acquire()

            log.debug(
                "Steam API request: URL=%s, Timeout=%s",
                url,
                request_timeout,
            )

            try:
                res = await aiohttp_session.get(
                    url,
                    headers={"user-agent": f"RomM/{get_version()}"},
                    timeout=ClientTimeout(total=request_timeout),
                )
                res.raise_for_status()
                body = await res.read()
                # A throttled storefront answers 200 with a bare `null`.
                if body.strip() == b"null":
                    return None
                return parse_response(tp, body, source=f"Steam {yarl.URL(url).name}")
            # A `total` timeout surfaces as a bare asyncio.TimeoutError, not as
            # aiohttp's ServerTimeoutError, so catch the base class.
            except TimeoutError:
                log.debug("Request to URL=%s timed out. Retrying...", url)
                continue
            except aiohttp.ClientConnectionError as exc:
                log.critical("Connection error: can't connect to Steam", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Can't connect to Steam, check your internet connection",
                ) from exc
            except aiohttp.ClientResponseError as exc:
                is_last_attempt = attempt == STEAM_MAX_REQUEST_ATTEMPTS - 1
                if (
                    exc.status == http.HTTPStatus.TOO_MANY_REQUESTS
                    and not is_last_attempt
                ):
                    log.warning(
                        "Steam rate limit hit, retrying after %ss",
                        STEAM_RATE_LIMIT_BACKOFF_SECONDS,
                    )
                    await asyncio.sleep(STEAM_RATE_LIMIT_BACKOFF_SECONDS)
                    continue

                log.error(exc)
                return None
            except json.JSONDecodeError as exc:
                log.error("Error decoding JSON response from Steam: %s", exc)
                return None

        return None

    async def search_apps(
        self,
        term: str,
        *,
        country: str = "us",
        language: str = "en",
    ) -> list[SteamStoreSearchItem]:
        """Search the storefront by name.

        Results include DLC, soundtracks and tools, so callers filter by type.
        """
        url = self.url.joinpath("storesearch").with_query(
            term=term, cc=country, l=language
        )
        response = await self._request(str(url), SteamStoreSearchResponse)
        return (response.get("items") or []) if response else []

    async def get_app_details(
        self,
        app_id: int,
        *,
        country: str = "us",
        language: str = "en",
        filters: str | None = None,
    ) -> SteamAppDetails | None:
        """Fetch the store page for a single app, or its `filters` sections.

        Returns None when Steam has no such app, or it is locked for `country`.
        """
        query = {"appids": str(app_id), "cc": country, "l": language}
        if filters:
            query["filters"] = filters
        url = self.url.joinpath("appdetails").with_query(query)
        response = await self._request(str(url), dict[str, SteamAppDetailsEnvelope])
        if not response:
            return None

        envelope = response.get(str(app_id))
        if envelope is None and len(response) == 1:
            envelope = self._envelope_keyed_by_another_id(response, app_id)
        if not envelope or not envelope.get("success"):
            return None

        return envelope.get("data")

    @staticmethod
    def _envelope_keyed_by_another_id(
        response: dict[str, SteamAppDetailsEnvelope], app_id: int
    ) -> SteamAppDetailsEnvelope | None:
        """Steam keys some apps' envelope by another ID, e.g. one of their DLC."""
        envelope = next(iter(response.values()))
        if not isinstance(envelope, dict):
            return None

        data = envelope.get("data")
        if not isinstance(data, dict) or data.get("steam_appid") != app_id:
            return None

        return envelope

    async def get_library_capsule_url(self, app_id: int) -> str | None:
        """The portrait capsule URL when the CDN serves one, else None."""
        return await self._probe_cdn_asset(
            STEAM_LIBRARY_CAPSULE_URL.format(app_id=app_id)
        )

    async def get_header_image_url(self, app_id: int) -> str | None:
        """The landscape header URL when the CDN serves one, else None."""
        return await self._probe_cdn_asset(STEAM_HEADER_IMAGE_URL.format(app_id=app_id))

    async def _probe_cdn_asset(self, asset_url: str) -> str | None:
        """Served by the CDN, not the storefront, so the probe skips the limiter."""
        aiohttp_session = ctx_aiohttp_session.get()

        try:
            res = await aiohttp_session.head(
                asset_url,
                headers={"user-agent": f"RomM/{get_version()}"},
                timeout=ClientTimeout(total=15),
                # aiohttp defaults HEAD to not following redirects, and the CDN
                # can answer an asset path with one.
                allow_redirects=True,
            )
        except (aiohttp.ClientError, TimeoutError) as exc:
            log.debug("Could not probe Steam asset %s: %s", asset_url, exc)
            return None

        return asset_url if res.status == 200 else None
