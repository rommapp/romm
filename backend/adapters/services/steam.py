import asyncio
import http
import json
from typing import Final, cast

import aiohttp
import yarl
from aiohttp.client import ClientTimeout
from fastapi import HTTPException, status

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

# The storefront publishes no rate limit, but it starts returning 429 at roughly
# 200 requests per 5 minutes per IP. Pace well under that, since a library scan
# spends two requests per game.
STEAM_MAX_REQUESTS_PER_SECOND: Final[float] = 0.6
STEAM_MAX_REQUEST_ATTEMPTS: Final[int] = 3
STEAM_RATE_LIMIT_BACKOFF_SECONDS: Final[float] = 5
_rate_limiter = RateLimiter(STEAM_MAX_REQUESTS_PER_SECOND)


class SteamService:
    """Service to interact with the Steam storefront API.

    Valve documents no storefront API. These two endpoints back the store's own
    search box and app pages, take no key, and are what ProtonDB and comparable
    tools read. They carry no compatibility promise, so every failure path here
    degrades to "no result" rather than aborting a scan.
    """

    def __init__(
        self,
        base_url: str | None = None,
    ) -> None:
        self.url = yarl.URL(base_url or "https://store.steampowered.com/api")

    async def _request(self, url: str, request_timeout: int = 120) -> dict:
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
                return await res.json()
            except aiohttp.ServerTimeoutError:
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
                return {}
            except json.JSONDecodeError as exc:
                log.error("Error decoding JSON response from Steam: %s", exc)
                return {}

        return {}

    async def search_apps(
        self,
        term: str,
        *,
        country: str = "us",
        language: str = "en",
    ) -> list[SteamStoreSearchItem]:
        """Search the storefront by name.

        Results include DLC, soundtracks and tools alongside games, so callers
        have to filter by type themselves.
        """
        url = self.url.joinpath("storesearch").with_query(
            term=term, cc=country, l=language
        )
        response = cast(SteamStoreSearchResponse, await self._request(str(url)))
        return response.get("items", []) or []

    async def get_app_details(
        self,
        app_id: int,
        *,
        country: str = "us",
        language: str = "en",
    ) -> SteamAppDetails | None:
        """Fetch the store page payload for a single app.

        Returns None when Steam has no such app, or when the app is region
        locked for the configured country.
        """
        url = self.url.joinpath("appdetails").with_query(
            appids=str(app_id), cc=country, l=language
        )
        response = await self._request(str(url))
        envelope = cast(SteamAppDetailsEnvelope | None, response.get(str(app_id)))
        if not envelope or not envelope.get("success"):
            return None

        return envelope.get("data")
