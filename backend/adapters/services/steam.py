import json
from typing import Final

import aiohttp
import yarl
from aiohttp.client import ClientTimeout
from fastapi import HTTPException

from adapters.services.provider_http import send_with_retries
from adapters.services.response_validation import parse_response
from adapters.services.steam_types import (
    SteamAppDetails,
    SteamAppDetailsEnvelope,
    SteamGlobalAchievementPercent,
    SteamGlobalAchievementPercentagesResponse,
    SteamOwnedGame,
    SteamOwnedGamesResponse,
    SteamPlayerAchievement,
    SteamPlayerAchievementsResponse,
    SteamPlayerSummariesResponse,
    SteamPlayerSummary,
    SteamSchemaAchievement,
    SteamSchemaForGameResponse,
    SteamStoreSearchItem,
    SteamStoreSearchResponse,
    SteamVanityResponse,
)
from config import STEAM_API_KEY
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

# The Web API allows 100,000 calls a day per key, with no documented burst limit.
STEAM_WEB_API_MAX_REQUESTS_PER_SECOND: Final[float] = 4
_web_api_rate_limiter = RateLimiter(STEAM_WEB_API_MAX_REQUESTS_PER_SECOND)
# ResolveVanityURL's `success` when the name belongs to a profile.
STEAM_VANITY_RESOLVED: Final[int] = 1
# GetPlayerAchievements' status for a game that has no stats.
STEAM_NO_STATS_STATUS: Final[int] = 400

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

        async def send() -> T | None:
            await _rate_limiter.acquire()
            log.debug(
                "Steam API request: URL=%s, Timeout=%s",
                url,
                request_timeout,
            )
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

        try:
            return await send_with_retries(
                send,
                provider="Steam",
                url=url,
                attempts=STEAM_MAX_REQUEST_ATTEMPTS,
                backoff=STEAM_RATE_LIMIT_BACKOFF_SECONDS,
            )
        except TimeoutError:
            log.debug("Request to URL=%s timed out on every attempt", url)
            return None
        except aiohttp.ClientResponseError as exc:
            log.error(exc)
            return None
        except json.JSONDecodeError as exc:
            log.error("Error decoding JSON response from Steam: %s", exc)
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


async def web_api_key_middleware(
    req: aiohttp.ClientRequest, handler: aiohttp.ClientHandlerType
) -> aiohttp.ClientResponse:
    """Add the key after the URL is logged, so it never reaches the logs."""
    req.url = req.url.update_query({"key": STEAM_API_KEY or ""})
    return await handler(req)


class SteamWebAPIError(Exception):
    """The Steam Web API refused a request or could not be reached."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class SteamWebApiService:
    """Service to interact with the keyed Steam Web API.

    Reference: https://partner.steamgames.com/doc/webapi/ISteamUserStats
    """

    def __init__(self, base_url: str | None = None) -> None:
        self.url = yarl.URL(base_url or "https://api.steampowered.com")

    async def _request[T](
        self, url: yarl.URL, tp: type[T], request_timeout: int = 60
    ) -> T:
        """Fetch one method's reply.

        Raises:
            SteamWebAPIError: Steam refused the request, could not be reached, or
                sent a reply that could not be read.
        """
        aiohttp_session = ctx_aiohttp_session.get()

        async def send() -> T | None:
            await _web_api_rate_limiter.acquire()
            log.debug("Steam Web API request: URL=%s", url)
            res = await aiohttp_session.get(
                url,
                headers={"user-agent": f"RomM/{get_version()}"},
                middlewares=(web_api_key_middleware,),
                timeout=ClientTimeout(total=request_timeout),
            )
            res.raise_for_status()
            # The path ends in the method name, then its version.
            return parse_response(
                tp, await res.read(), source=f"Steam Web API {url.parent.parent.name}"
            )

        try:
            response = await send_with_retries(
                send,
                provider="Steam Web API",
                url=str(url),
                attempts=STEAM_MAX_REQUEST_ATTEMPTS,
                backoff=STEAM_RATE_LIMIT_BACKOFF_SECONDS,
            )
        except TimeoutError as exc:
            raise SteamWebAPIError("Steam did not answer in time") from exc
        # A connection failure arrives as the 503 `send_with_retries` raises.
        except HTTPException as exc:
            raise SteamWebAPIError("Can't connect to Steam") from exc
        except aiohttp.ClientResponseError as exc:
            if exc.status in (401, 403):
                raise SteamWebAPIError(
                    "Steam rejected the API key", status=exc.status
                ) from exc
            raise SteamWebAPIError(
                f"Steam answered with HTTP {exc.status}", status=exc.status
            ) from exc
        # Also a truncated body, or one that is not UTF-8 JSON.
        except (aiohttp.ClientError, ValueError) as exc:
            raise SteamWebAPIError("Steam sent a reply that could not be read") from exc

        if response is None:
            raise SteamWebAPIError("Steam sent a reply that could not be read")
        return response

    async def _optional_request[T](self, url: yarl.URL, tp: type[T]) -> T | None:
        """Fetch an optional extra, logging a failure instead of raising it."""
        try:
            return await self._request(url, tp)
        except SteamWebAPIError as exc:
            log.error("Steam Web API %s failed: %s", url.parent.parent.name, exc)
            return None

    async def get_schema_achievements(
        self, app_id: int, *, language: str = "english"
    ) -> list[SteamSchemaAchievement]:
        """The app's achievements in the developer's order, empty if none or unreadable."""
        url = self.url.joinpath("ISteamUserStats/GetSchemaForGame/v2/").with_query(
            appid=str(app_id), l=language
        )
        response = await self._optional_request(url, SteamSchemaForGameResponse)
        if not response:
            return []

        stats = response.get("game", {}).get("availableGameStats", {})
        return stats.get("achievements") or []

    async def get_global_achievement_percentages(
        self, app_id: int
    ) -> list[SteamGlobalAchievementPercent]:
        """The share of players holding each achievement, empty if unreadable."""
        url = self.url.joinpath(
            "ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/"
        ).with_query(gameid=str(app_id))
        response = await self._optional_request(
            url, SteamGlobalAchievementPercentagesResponse
        )
        if not response:
            return []

        return response.get("achievementpercentages", {}).get("achievements") or []

    async def resolve_vanity_url(self, vanity_name: str) -> str | None:
        """The SteamID64 behind a custom profile URL name, or None if unused."""
        url = self.url.joinpath("ISteamUser/ResolveVanityURL/v1/").with_query(
            vanityurl=vanity_name
        )
        result = (await self._request(url, SteamVanityResponse)).get("response", {})
        if result.get("success") != STEAM_VANITY_RESOLVED:
            return None
        return result.get("steamid")

    async def get_player_summary(self, steam_id: str) -> SteamPlayerSummary | None:
        """The public profile of a SteamID64, or None if no account has it."""
        url = self.url.joinpath("ISteamUser/GetPlayerSummaries/v2/").with_query(
            steamids=steam_id
        )
        response = await self._request(url, SteamPlayerSummariesResponse)
        players = response.get("response", {}).get("players", [])
        return players[0] if players else None

    async def get_owned_games(self, steam_id: str) -> list[SteamOwnedGame] | None:
        """Every game the account owns, or None when its game details are private."""
        url = self.url.joinpath("IPlayerService/GetOwnedGames/v1/").with_query(
            steamid=steam_id, include_appinfo="1", include_played_free_games="1"
        )
        result = (await self._request(url, SteamOwnedGamesResponse)).get("response", {})
        if "game_count" not in result:
            return None
        return result.get("games", [])

    async def get_player_achievements(
        self, steam_id: str, app_id: int
    ) -> list[SteamPlayerAchievement]:
        """A player's state on each achievement of a game, empty if it has none.

        Raises:
            SteamWebAPIError: Steam refused the request (a 403 when the player's
                game details are private) or could not be reached.
        """
        url = self.url.joinpath("ISteamUserStats/GetPlayerAchievements/v1/").with_query(
            steamid=steam_id, appid=str(app_id)
        )
        try:
            response = await self._request(url, SteamPlayerAchievementsResponse)
        except SteamWebAPIError as exc:
            if exc.status == STEAM_NO_STATS_STATUS:
                return []
            raise
        # A reply that strays from its TypedDict is handed back as sent.
        stats = response.get("playerstats")
        achievements = stats.get("achievements") if isinstance(stats, dict) else None
        return achievements if isinstance(achievements, list) else []
