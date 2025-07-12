import http
import itertools
import json
from collections.abc import AsyncIterator, Collection
from typing import Literal, cast

import aiohttp
import yarl
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
from aiohttp.client import ClientTimeout
from config import STEAMGRIDDB_API_KEY
from exceptions.endpoint_exceptions import SGDBInvalidAPIKeyException
from logger.logger import log
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

    def __init__(self) -> None:
        self.api_url = yarl.URL("https://steamgriddb.com/api/v2")
        self.public_url = yarl.URL("https://www.steamgriddb.com/api/public")

    async def _request(
        self,
        url: str,
        method: str = "GET",
        headers: dict | None = None,
        json_data: dict | None = None,
        request_timeout: int = 120,
    ) -> dict:
        aiohttp_session = ctx_aiohttp_session.get()
        log.debug(
            "API request: Method=%s, URL=%s, Timeout=%s",
            method.upper(),
            url,
            request_timeout,
        )

        # Prepare request kwargs
        request_kwargs = {
            "middlewares": (auth_middleware,),
            "timeout": ClientTimeout(total=request_timeout),
        }

        # Add headers if provided
        if headers:
            request_kwargs["headers"] = headers

        # Add JSON data for POST requests
        if method.upper() == "POST" and json_data:
            request_kwargs["json"] = json_data

        try:
            # Use the appropriate HTTP method
            if method.upper() == "GET":
                res = await aiohttp_session.get(url, **request_kwargs)
            elif method.upper() == "POST":
                res = await aiohttp_session.post(url, **request_kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            res.raise_for_status()
            return await res.json()

        except aiohttp.ClientResponseError as exc:
            if exc.status == http.HTTPStatus.UNAUTHORIZED:
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
        params: dict[str, list[str]] = {
            "game_id": [str(game_id)],
        }
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

        url = self.public_url.joinpath("search/assets")
        response = await self._request(str(url), method="POST", json_data=params)
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
        url = self.api_url.joinpath("search/autocomplete", term)
        response = await self._request(str(url))
        return cast(list[SGDBGame], response.get("data", []))
