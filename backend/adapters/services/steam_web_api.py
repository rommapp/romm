import json
from typing import Final

import aiohttp
import yarl
from aiohttp.client import ClientTimeout
from fastapi import HTTPException

from adapters.services.provider_http import send_with_retries
from adapters.services.response_validation import parse_response
from adapters.services.steam_types import (
    SteamOwnedGame,
    SteamOwnedGamesResponse,
    SteamPlayerSummariesResponse,
    SteamPlayerSummary,
    SteamVanityResponse,
)
from logger.logger import log
from utils import get_version
from utils.context import ctx_aiohttp_session

STEAM_WEB_API_URL: Final[str] = "https://api.steampowered.com"
STEAM_VANITY_RESOLVED: Final[int] = 1
STEAM_PROFILE_PUBLIC: Final[int] = 3


class SteamWebAPIError(Exception):
    """The Steam Web API refused a request or could not be reached."""


class SteamWebAPIService:
    """Client for the keyed Steam Web API, which reads a player's account."""

    def __init__(self, api_key: str, base_url: str | None = None) -> None:
        self.api_key = api_key
        self.url = yarl.URL(base_url or STEAM_WEB_API_URL)

    async def _request[T](
        self, path: str, tp: type[T], params: dict[str, str], request_timeout: int = 60
    ) -> T:
        aiohttp_session = ctx_aiohttp_session.get()
        url = self.url.joinpath(path).with_query({**params, "key": self.api_key})

        async def send() -> T | None:
            # The query carries the API key, so only the path is logged.
            log.debug("Steam Web API request: %s", path)
            res = await aiohttp_session.get(
                url,
                headers={"user-agent": f"RomM/{get_version()}"},
                timeout=ClientTimeout(total=request_timeout),
            )
            res.raise_for_status()
            return parse_response(tp, await res.read(), source=f"Steam {path}")

        try:
            response = await send_with_retries(send, provider="Steam", url=path)
        except TimeoutError as exc:
            raise SteamWebAPIError("Steam did not answer in time") from exc
        except HTTPException as exc:
            raise SteamWebAPIError("Can't connect to Steam") from exc
        except json.JSONDecodeError as exc:
            raise SteamWebAPIError("Steam sent a reply that could not be read") from exc
        except aiohttp.ClientResponseError as exc:
            if exc.status in (401, 403):
                raise SteamWebAPIError("Steam rejected the API key") from exc
            raise SteamWebAPIError(f"Steam answered with HTTP {exc.status}") from exc

        if response is None:
            raise SteamWebAPIError("Steam sent a reply that could not be read")
        return response

    async def resolve_vanity_url(self, vanity_name: str) -> str | None:
        """The SteamID64 behind a custom profile URL name, or None if unused."""
        response = await self._request(
            "ISteamUser/ResolveVanityURL/v1/",
            SteamVanityResponse,
            {"vanityurl": vanity_name},
        )
        result = response.get("response", {})
        if result.get("success") != STEAM_VANITY_RESOLVED:
            return None
        return result.get("steamid")

    async def get_player_summary(self, steam_id: str) -> SteamPlayerSummary | None:
        """The public profile of a SteamID64, or None if no account has it."""
        response = await self._request(
            "ISteamUser/GetPlayerSummaries/v2/",
            SteamPlayerSummariesResponse,
            {"steamids": steam_id},
        )
        players = response.get("response", {}).get("players", [])
        return players[0] if players else None

    async def get_owned_games(self, steam_id: str) -> list[SteamOwnedGame] | None:
        """Every game the account owns, or None when its game details are private."""
        response = await self._request(
            "IPlayerService/GetOwnedGames/v1/",
            SteamOwnedGamesResponse,
            {
                "steamid": steam_id,
                "include_appinfo": "1",
                "include_played_free_games": "1",
            },
        )
        result = response.get("response", {})
        if "game_count" not in result:
            return None
        return result.get("games", [])
