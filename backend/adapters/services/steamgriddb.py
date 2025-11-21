import http
import itertools
import json
from collections.abc import AsyncIterator, Collection
from typing import Literal, cast

import aiohttp
import aiohttp.client_exceptions
import yarl
from aiohttp.client import ClientTimeout

from adapters.services.steamgriddb_types import (
    SGDBDimension,
    SGDBGame,
    SGDBGrid,
    SGDBGridList,
    SGDBMime,
    SGDBStyle,
    SGDBTag,
    SGDBType,
)
from config import STEAMGRIDDB_API_KEY
from exceptions.endpoint_exceptions import SGDBInvalidAPIKeyException
from logger.logger import log
from utils import get_version
from utils.context import ctx_aiohttp_session


async def auth_middleware(
    req: aiohttp.ClientRequest, handler: aiohttp.ClientHandlerType
) -> aiohttp.ClientResponse:
    """SteamGridDB API authentication mechanism."""
    req.headers["Authorization"] = f"Bearer {STEAMGRIDDB_API_KEY}"
    return await handler(req)


class SteamGridDBService:
    """Service to interact with the SteamGridDB API.

    Reference: https://www.steamgriddb.com/api/v2
    """

    def __init__(
        self,
        base_url: str | None = None,
    ) -> None:
        self.url = yarl.URL(base_url or "https://steamgriddb.com/api/v2")

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
        except aiohttp.client_exceptions.ClientResponseError as exc:
            log.warning(f"Request failed with status {exc.status} for URL: {url}")
            if exc.status == http.HTTPStatus.UNAUTHORIZED:
                log.warning("Invalid API key or unauthorized access.")
                raise SGDBInvalidAPIKeyException from exc
            # Log the error and return an empty dict if the request fails with a different code
            log.error(exc)
            return {}
        except json.decoder.JSONDecodeError as exc:
            log.error(
                "Failed to decode JSON response from SteamGridDB: %s",
                str(exc),
            )
            return {}

    async def get_grids_for_game(
        self,
        game_id: int,
        *,
        styles: Collection[SGDBStyle] | None = None,
        dimensions: Collection[SGDBDimension] | None = None,
        mimes: Collection[SGDBMime] | None = None,
        types: Collection[SGDBType] | None = None,
        any_of_tags: Collection[SGDBTag] | None = None,
        is_nsfw: bool | Literal["any"] | None = None,
        is_humor: bool | Literal["any"] | None = None,
        is_epilepsy: bool | Literal["any"] | None = None,
        limit: int | None = None,
        page_number: int | None = None,
    ) -> SGDBGridList:
        """Retrieve grids by game ID.

        Reference: https://www.steamgriddb.com/api/v2#tag/GRIDS/operation/getGridsByGameId
        """
        params: dict[str, list[str]] = {}
        if styles:
            params["styles"] = [",".join(styles)]
        if dimensions:
            params["dimensions"] = [",".join(dimensions)]
        if mimes:
            params["mimes"] = [",".join(mimes)]
        if types:
            params["types"] = [",".join(types)]
        if any_of_tags:
            params["oneoftag"] = [",".join(any_of_tags)]
        if is_nsfw is not None:
            params["nsfw"] = [str(is_nsfw).lower()]
        if is_humor is not None:
            params["humor"] = [str(is_humor).lower()]
        if is_epilepsy is not None:
            params["epilepsy"] = [str(is_epilepsy).lower()]
        if limit is not None:
            params["limit"] = [str(limit)]
        if page_number is not None:
            params["page"] = [str(page_number)]

        base_url = self.url.joinpath("grids/game", str(game_id))
        url = base_url.with_query(**params) if params else base_url
        response = await self._request(str(url))
        if not response:
            return SGDBGridList(
                page=0,
                total=0,
                limit=limit or 50,
                data=[],
            )
        return cast(SGDBGridList, response)

    async def iter_grids_for_game(
        self,
        game_id: int,
        *,
        styles: Collection[SGDBStyle] | None = None,
        dimensions: Collection[SGDBDimension] | None = None,
        mimes: Collection[SGDBMime] | None = None,
        types: Collection[SGDBType] | None = None,
        any_of_tags: Collection[SGDBTag] | None = None,
        is_nsfw: bool | Literal["any"] | None = None,
        is_humor: bool | Literal["any"] | None = None,
        is_epilepsy: bool | Literal["any"] | None = None,
    ) -> AsyncIterator[SGDBGrid]:
        """Iterate through grids by game ID.

        Reference: https://www.steamgriddb.com/api/v2#tag/GRIDS/operation/getGridsByGameId
        """
        page_size = 50  # Maximum page size for this endpoint.
        offset = 0

        for page_number in itertools.count(start=0):
            response = await self.get_grids_for_game(
                game_id,
                styles=styles,
                dimensions=dimensions,
                mimes=mimes,
                types=types,
                any_of_tags=any_of_tags,
                is_nsfw=is_nsfw,
                is_humor=is_humor,
                is_epilepsy=is_epilepsy,
                limit=page_size,
                page_number=page_number,
            )
            results = response["data"]
            for result in results:
                yield result

            offset += len(results)
            if len(results) < page_size or offset >= response["total"]:
                break

    async def search_games(self, term: str) -> list[SGDBGame]:
        """Search for games by name.

        Reference: https://www.steamgriddb.com/api/v2#tag/SEARCH/operation/searchGrids
        """
        url = self.url.joinpath("search/autocomplete", term)
        response = await self._request(str(url))
        return cast(list[SGDBGame], response.get("data", []))

    async def get_game_by_id(self, game_id: int) -> SGDBGame | None:
        """Get game details by ID.

        Reference: https://www.steamgriddb.com/api/v2#tag/GAMES/operation/getGameById
        """
        url = self.url.joinpath("games/id", str(game_id))
        response = await self._request(str(url))
        if not response or "data" not in response:
            return None
        return cast(SGDBGame, response["data"])
