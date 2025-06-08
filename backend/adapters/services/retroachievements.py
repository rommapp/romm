import asyncio
import http
from typing import Generator, cast

import httpx
import yarl
from adapters.services.retroachievements_types import (
    RAGameExtendedDetails,
    RAGameInfoAndUserProgress,
    RAGameListItem,
    RAUserCompletionProgress,
)
from config import RETROACHIEVEMENTS_API_KEY
from fastapi import HTTPException, status
from logger.logger import log
from utils.context import ctx_httpx_client


class RetroAchievementsAuth(httpx.Auth):
    """RetroAchievements API authentication class.

    Reference: https://api-docs.retroachievements.org/getting-started.html#quick-start-http-requests
    """

    def __init__(self, token: str):
        self.token = token

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        request.url = request.url.copy_merge_params({"y": self.token})
        yield request


class RetroAchievementsService:
    """Service to interact with the RetroAchievements API.

    Reference: https://api-docs.retroachievements.org/
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str = RETROACHIEVEMENTS_API_KEY,
    ) -> None:
        self.url = yarl.URL(base_url or "https://retroachievements.org/API")
        self.token = token

    @property
    def _auth(self) -> httpx.Auth:
        return RetroAchievementsAuth(token=self.token)

    async def _request(self, url: str, request_timeout: int = 120) -> dict:
        httpx_client = ctx_httpx_client.get()
        log.debug(
            "API request: URL=%s, Timeout=%s",
            url,
            request_timeout,
        )
        try:
            res = await httpx_client.get(url, auth=self._auth, timeout=request_timeout)
            res.raise_for_status()
            return res.json()
        except httpx.NetworkError as exc:
            log.critical(
                "Connection error: can't connect to RetroAchievements", exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to RetroAchievements, check your internet connection",
            ) from exc
        except httpx.HTTPStatusError as err:
            if err.response.status_code == http.HTTPStatus.TOO_MANY_REQUESTS:
                # Retry after 2 seconds if rate limit hit
                await asyncio.sleep(2)
            else:
                # Log the error and return an empty dict if the request fails with a different code
                log.error(err)
                return {}
        except httpx.TimeoutException:
            # Retry the request once if it times out
            pass

        try:
            log.debug(
                "API request: URL=%s, Timeout=%s",
                url,
                request_timeout,
            )
            res = await httpx_client.get(url, auth=self._auth, timeout=request_timeout)
            res.raise_for_status()
        except (httpx.HTTPStatusError, httpx.TimeoutException) as err:
            if (
                isinstance(err, httpx.HTTPStatusError)
                and err.response.status_code == http.HTTPStatus.UNAUTHORIZED
            ):
                return {}

            log.error(err)
            return {}

        return res.json()

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
