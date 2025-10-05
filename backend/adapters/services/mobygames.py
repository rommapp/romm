import asyncio
import http
import json
from collections.abc import Collection
from typing import Literal, overload

import aiohttp
import yarl
from aiohttp.client import ClientTimeout
from fastapi import HTTPException, status

from adapters.services.mobygames_types import MobyGame, MobyGameBrief, MobyOutputFormat
from config import MOBYGAMES_API_KEY
from logger.logger import log
from utils import get_version
from utils.context import ctx_aiohttp_session


async def auth_middleware(
    req: aiohttp.ClientRequest, handler: aiohttp.ClientHandlerType
) -> aiohttp.ClientResponse:
    """MobyGames API authentication mechanism."""
    req.url = req.url.update_query({"api_key": MOBYGAMES_API_KEY})
    return await handler(req)


class MobyGamesService:
    """Service to interact with the MobyGames API.

    Reference: https://www.mobygames.com/info/api/
    """

    def __init__(
        self,
        base_url: str | None = None,
    ) -> None:
        self.url = yarl.URL(base_url or "https://api.mobygames.com/v1")

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
            log.debug("Request to URL=%s timed out. Retrying...", url)
        except aiohttp.ClientConnectionError as exc:
            log.critical("Connection error: can't connect to MobyGames", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to MobyGames, check your internet connection",
            ) from exc
        except aiohttp.ClientResponseError as exc:
            if exc.status == http.HTTPStatus.UNAUTHORIZED:
                # Sometimes MobyGames returns 401 even with a valid API key
                log.error(exc)
                return {}
            elif exc.status == http.HTTPStatus.TOO_MANY_REQUESTS:
                # Retry after 2 seconds if rate limit hit
                await asyncio.sleep(2)
            else:
                # Log the error and return an empty dict if the request fails with a different code
                log.error(exc)
                return {}
        except json.JSONDecodeError as exc:
            log.error("Error decoding JSON response from ScreenScraper: %s", exc)
            return {}

        # Retry the request once if it times out
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
        except (aiohttp.ClientResponseError, aiohttp.ServerTimeoutError) as exc:
            if (
                isinstance(exc, aiohttp.ClientResponseError)
                and exc.status == http.HTTPStatus.UNAUTHORIZED
            ):
                return {}

            log.error(exc)
            return {}
        except json.JSONDecodeError as exc:
            log.error("Error decoding JSON response from ScreenScraper: %s", exc)
            return {}

    async def list_groups(self, limit: int | None = None) -> list[dict]:
        """Retrieve a list of groups.

        Reference: https://www.mobygames.com/info/api/#groups
        """
        params: dict[str, list[str]] = {}
        if limit is not None:
            params["limit"] = [str(limit)]

        url = self.url.joinpath("groups").with_query(**params)
        response = await self._request(str(url))
        return response.get("groups", [])

    @overload
    async def list_games(
        self,
        *,
        game_id: int | None = ...,
        platform_ids: Collection[int] | None = ...,
        genre_ids: Collection[int] | None = ...,
        group_ids: Collection[int] | None = ...,
        title: str | None = ...,
        output_format: Literal["id"],
        limit: int | None = ...,
        offset: int | None = ...,
    ) -> list[int]: ...

    @overload
    async def list_games(
        self,
        *,
        game_id: int | None = ...,
        platform_ids: Collection[int] | None = ...,
        genre_ids: Collection[int] | None = ...,
        group_ids: Collection[int] | None = ...,
        title: str | None = ...,
        output_format: Literal["brief"],
        limit: int | None = ...,
        offset: int | None = ...,
    ) -> list[MobyGameBrief]: ...

    @overload
    async def list_games(
        self,
        *,
        game_id: int | None = ...,
        platform_ids: Collection[int] | None = ...,
        genre_ids: Collection[int] | None = ...,
        group_ids: Collection[int] | None = ...,
        title: str | None = ...,
        output_format: Literal["normal"] = "normal",
        limit: int | None = ...,
        offset: int | None = ...,
    ) -> list[MobyGame]: ...

    async def list_games(
        self,
        *,
        game_id: int | None = None,
        platform_ids: Collection[int] | None = None,
        genre_ids: Collection[int] | None = None,
        group_ids: Collection[int] | None = None,
        title: str | None = None,
        output_format: MobyOutputFormat = "normal",
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[int] | list[MobyGameBrief] | list[MobyGame]:
        """Provides a list of games matching the filters given in the query parameters, ordered by ID.

        Reference: https://www.mobygames.com/info/api/#games
        """
        params: dict[str, list[str]] = {}
        if game_id:
            params["id"] = [str(game_id)]
        if platform_ids:
            params["platform"] = [str(id_) for id_ in platform_ids]
        if genre_ids:
            params["genre"] = [str(id_) for id_ in genre_ids]
        if group_ids:
            params["group"] = [str(id_) for id_ in group_ids]
        if title:
            params["title"] = [title]
        if output_format:
            params["format"] = [output_format]
        if limit is not None:
            params["limit"] = [str(limit)]
        if offset is not None:
            params["offset"] = [str(offset)]

        url = self.url.joinpath("games").with_query(**params)
        response = await self._request(str(url))
        return response.get("games", [])
