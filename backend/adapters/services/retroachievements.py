import asyncio
import http
import json
from collections.abc import AsyncIterator
from typing import cast

import aiohttp
import yarl
from aiohttp.client import ClientTimeout
from fastapi import HTTPException, status

from adapters.services.retroachievements_types import (
    RAGameExtendedDetails,
    RAGameInfoAndUserProgress,
    RAGameListItem,
    RAUserCompletionProgress,
    RAUserCompletionProgressResult,
)
from config import RETROACHIEVEMENTS_API_KEY
from logger.logger import log
from utils import get_version
from utils.context import ctx_aiohttp_session


async def auth_middleware(
    req: aiohttp.ClientRequest, handler: aiohttp.ClientHandlerType
) -> aiohttp.ClientResponse:
    """RetroAchievements API authentication mechanism.

    Reference: https://api-docs.retroachievements.org/getting-started.html#quick-start-http-requests
    """
    req.url = req.url.update_query({"y": RETROACHIEVEMENTS_API_KEY})
    return await handler(req)


class RetroAchievementsService:
    """Service to interact with the RetroAchievements API.

    Reference: https://api-docs.retroachievements.org/
    """

    def __init__(
        self,
        base_url: str | None = None,
    ) -> None:
        self.url = yarl.URL(base_url or "https://retroachievements.org/API")

    async def _request(self, url: str, request_timeout: int = 120) -> dict:
        aiohttp_session = ctx_aiohttp_session.get()
        log.debug(
            "API request: URL=%s, Timeout=%s",
            url,
            request_timeout,
        )
        try:
            res = await aiohttp_session.get(
                url,
                headers={"user-agent": f"RomM/{get_version()}"},
                middlewares=(auth_middleware,),
                timeout=ClientTimeout(total=request_timeout),
            )
            res.raise_for_status()
            return await res.json()
        except aiohttp.ServerTimeoutError:
            # Retry the request once if it times out
            pass
        except aiohttp.ClientConnectionError as exc:
            log.critical(
                "Connection error: can't connect to RetroAchievements", exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to RetroAchievements, check your internet connection",
            ) from exc
        except aiohttp.ClientResponseError as err:
            if err.status == http.HTTPStatus.TOO_MANY_REQUESTS:
                # Retry after 2 seconds if rate limit hit
                await asyncio.sleep(2)
            else:
                # Log the error and return an empty dict if the request fails with a different code
                log.error(err)
                return {}
        except json.JSONDecodeError as exc:
            log.error("Error decoding JSON response from ScreenScraper: %s", exc)
            return {}

        try:
            log.debug(
                "API request: URL=%s, Timeout=%s",
                url,
                request_timeout,
            )
            res = await aiohttp_session.get(
                url,
                headers={"user-agent": f"RomM/{get_version()}"},
                middlewares=(auth_middleware,),
                timeout=ClientTimeout(total=request_timeout),
            )
            res.raise_for_status()
            return await res.json()
        except (aiohttp.ClientResponseError, aiohttp.ServerTimeoutError) as err:
            if (
                isinstance(err, aiohttp.ClientResponseError)
                and err.status == http.HTTPStatus.UNAUTHORIZED
            ):
                return {}

            log.error(err)
            return {}
        except json.JSONDecodeError as exc:
            log.error("Error decoding JSON response from ScreenScraper: %s", exc)
            return {}

    async def get_achievement_of_the_week(self) -> dict:
        """Retrieve the achievement of the week.

        Reference: https://api-docs.retroachievements.org/v1/get-achievement-of-the-week.html
        """
        url = self.url.joinpath("API_GetAchievementOfTheWeek.php")
        response = await self._request(str(url))
        return response

    async def get_game_extended_details(self, game_id: int) -> RAGameExtendedDetails:
        """Retrieve extended metadata about a game, targeted via its unique ID.

        Reference: https://api-docs.retroachievements.org/v1/get-game-extended.html
        """
        url = self.url.joinpath("API_GetGameExtended.php").with_query(
            i=[game_id],
        )
        response = await self._request(str(url))
        return cast(RAGameExtendedDetails, response)

    async def get_game_list(
        self,
        system_id: int,
        *,
        only_games_with_achievements: bool = False,
        include_hashes: bool = False,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[RAGameListItem]:
        """Retrieve the complete list of games for a specified console on the site, targeted by the console ID.

        Reference: https://api-docs.retroachievements.org/v1/get-game-list.html
        """
        params: dict[str, list[str]] = {"i": [str(system_id)]}
        if only_games_with_achievements:
            params["f"] = ["1"]
        if include_hashes:
            params["h"] = ["1"]
        if limit is not None:
            params["c"] = [str(limit)]
        if offset is not None:
            params["o"] = [str(offset)]

        url = self.url.joinpath("API_GetGameList.php").with_query(**params)
        response = await self._request(str(url))
        return cast(list[RAGameListItem], response)

    async def get_user_completion_progress(
        self,
        username: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> RAUserCompletionProgress:
        """Retrieve a given user's completion progress, targeted by their username.

        Reference: https://api-docs.retroachievements.org/v1/get-user-completion-progress.html
        """
        params: dict[str, list[str]] = {"u": [username]}
        if limit is not None:
            params["c"] = [str(limit)]
        if offset is not None:
            params["o"] = [str(offset)]

        url = self.url.joinpath("API_GetUserCompletionProgress.php").with_query(
            **params
        )
        response = await self._request(str(url))
        return cast(RAUserCompletionProgress, response)

    async def iter_user_completion_progress(
        self,
        username: str,
    ) -> AsyncIterator[RAUserCompletionProgressResult]:
        """Iterate through a given user's completion progress, targeted by their username.

        Reference: https://api-docs.retroachievements.org/v1/get-user-completion-progress.html
        """
        page_size = 500  # Maximum page size for this endpoint.
        offset = 0

        while True:
            response = await self.get_user_completion_progress(
                username,
                limit=page_size,
                offset=offset or None,
            )
            results = response["Results"]
            for result in results:
                yield result

            offset += len(results)
            if len(results) < page_size or offset >= response["Total"]:
                break

    async def get_user_game_progress(
        self,
        username: str,
        game_id: int,
        *,
        include_award_metadata: bool = False,
    ) -> RAGameInfoAndUserProgress:
        """Retrieve extended metadata about a game, in addition to a user's progress about that game.

        Reference: https://api-docs.retroachievements.org/v1/get-game-info-and-user-progress.html
        """
        params: dict[str, list[str]] = {
            "u": [username],
            "g": [str(game_id)],
        }
        if include_award_metadata:
            params["a"] = ["1"]

        url = self.url.joinpath("API_GetGameInfoAndUserProgress.php").with_query(
            **params
        )
        response = await self._request(str(url))
        return cast(RAGameInfoAndUserProgress, response)
