import json
from collections.abc import AsyncIterator
from typing import Any, Final, get_origin

import aiohttp
import yarl
from aiohttp.client import ClientTimeout
from fastapi import HTTPException, status

from adapters.services.provider_http import send_with_retries
from adapters.services.response_validation import parse_response
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
from utils.rate_limiter import RateLimiter

# RetroAchievements does not publish a fixed limit, try to stay
# within the "fair burst" allowance the API documents
RA_MAX_REQUESTS_PER_SECOND: Final[float] = 4
RA_MIN_REQUESTS_PER_SECOND: Final[float] = 0.5
# Pace regained per request that goes through after a 429 halved it.
RA_RECOVERY_REQUESTS_PER_SECOND: Final[float] = 0.25
_rate_limiter = RateLimiter(RA_MAX_REQUESTS_PER_SECOND)
# A progress sync sends one request per game, so its requests ride out a throttled burst.
RA_SYNC_RATE_LIMIT_ATTEMPTS: Final[int] = 5
# Status codes that mean RA itself is unavailable, not that it refused this request.
RA_UNAVAILABLE_STATUSES: Final = frozenset(
    {
        status.HTTP_429_TOO_MANY_REQUESTS,
        status.HTTP_502_BAD_GATEWAY,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        status.HTTP_504_GATEWAY_TIMEOUT,
    }
)


class RARequestRejectedError(HTTPException):
    """RA answered this one request with an error or an unreadable reply."""


def _throttle(delay: float) -> None:
    """Hold every RA request through a 429's wait, then resume at half the pace."""
    _rate_limiter.hold(delay)
    _rate_limiter.set_requests_per_second(
        max(_rate_limiter.requests_per_second / 2, RA_MIN_REQUESTS_PER_SECOND)
    )


def _recover() -> None:
    pace = _rate_limiter.requests_per_second
    if pace < RA_MAX_REQUESTS_PER_SECOND:
        _rate_limiter.set_requests_per_second(
            min(pace + RA_RECOVERY_REQUESTS_PER_SECOND, RA_MAX_REQUESTS_PER_SECOND)
        )


async def auth_middleware(
    req: aiohttp.ClientRequest, handler: aiohttp.ClientHandlerType
) -> aiohttp.ClientResponse:
    """RetroAchievements API authentication mechanism.

    Reference: https://api-docs.retroachievements.org/getting-started.html#quick-start-http-requests
    """
    req.url = req.url.update_query({"y": RETROACHIEVEMENTS_API_KEY or ""})
    return await handler(req)


def _failed(reason: Exception) -> HTTPException:
    log.error("RetroAchievements request failed: %s", reason)
    rejected = isinstance(reason, json.JSONDecodeError) or (
        isinstance(reason, aiohttp.ClientResponseError)
        and reason.status not in RA_UNAVAILABLE_STATUSES
    )
    return (RARequestRejectedError if rejected else HTTPException)(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="RetroAchievements did not answer the request, try again later",
    )


def _parse[T](tp: type[T], body: bytes, *, source: str) -> T | None:
    # RA answers an unknown id with 200 and an empty list.
    if body.strip() == b"[]" and get_origin(tp) is not list:
        return None
    return parse_response(tp, body, source=source)


class RetroAchievementsService:
    """Service to interact with the RetroAchievements API.

    Reference: https://api-docs.retroachievements.org/
    """

    def __init__(
        self,
        base_url: str | None = None,
    ) -> None:
        self.url = yarl.URL(base_url or "https://retroachievements.org/API")

    async def _request[T](
        self,
        url: str,
        tp: type[T],
        request_timeout: float = 120,
        rate_limit_attempts: int | None = None,
    ) -> T | None:
        """Fetch one endpoint, raising a 503 when the request fails.

        Returns:
            The decoded reply, or None when RA has no such entity.

        Raises:
            RARequestRejectedError: RA refused this request but is up.
            HTTPException: RA is unavailable or throttling.
        """
        source = f"RetroAchievements {yarl.URL(url).name}"
        aiohttp_session = ctx_aiohttp_session.get()

        async def send() -> T | None:
            log.debug(
                "API request: URL=%s, Timeout=%s",
                url,
                request_timeout,
            )
            await _rate_limiter.acquire()
            res = await aiohttp_session.get(
                url,
                headers={"user-agent": f"RomM/{get_version()}"},
                middlewares=(auth_middleware,),
                timeout=ClientTimeout(total=request_timeout),
            )
            res.raise_for_status()
            _recover()
            return _parse(tp, await res.read(), source=source)

        try:
            return await send_with_retries(
                send,
                provider="RetroAchievements",
                url=url,
                rate_limit_attempts=rate_limit_attempts,
                on_rate_limit=_throttle,
            )
        except (
            aiohttp.ClientResponseError,
            TimeoutError,
            json.JSONDecodeError,
        ) as err:
            raise _failed(err) from err

    async def get_achievement_of_the_week(self) -> dict[str, Any] | None:
        """Retrieve the achievement of the week.

        Reference: https://api-docs.retroachievements.org/v1/get-achievement-of-the-week.html
        """
        url = self.url.joinpath("API_GetAchievementOfTheWeek.php")
        return await self._request(str(url), dict[str, Any])

    async def get_game_extended_details(
        self, game_id: int
    ) -> RAGameExtendedDetails | None:
        """Retrieve extended metadata about a game, targeted via its unique ID.

        Reference: https://api-docs.retroachievements.org/v1/get-game-extended.html
        """
        url = self.url.joinpath("API_GetGameExtended.php").with_query(
            i=[game_id],
        )
        return await self._request(str(url), RAGameExtendedDetails)

    async def get_game_list(
        self,
        system_id: int,
        *,
        only_games_with_achievements: bool = False,
        include_hashes: bool = False,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[RAGameListItem] | None:
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
        return await self._request(str(url), list[RAGameListItem])

    async def get_user_completion_progress(
        self,
        username: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> RAUserCompletionProgress | None:
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
        return await self._request(
            str(url),
            RAUserCompletionProgress,
            rate_limit_attempts=RA_SYNC_RATE_LIMIT_ATTEMPTS,
        )

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
            if response is None:
                break
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
    ) -> RAGameInfoAndUserProgress | None:
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
        return await self._request(
            str(url),
            RAGameInfoAndUserProgress,
            rate_limit_attempts=RA_SYNC_RATE_LIMIT_ATTEMPTS,
        )
