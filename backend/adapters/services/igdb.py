import asyncio
import http
import json
from collections.abc import Sequence
from functools import partial
from typing import TYPE_CHECKING

import aiohttp
import yarl
from aiohttp.client import ClientTimeout
from fastapi import HTTPException, status
from unidecode import unidecode

from adapters.services.igdb_types import Game
from config import IGDB_CLIENT_ID
from logger.logger import log
from utils import get_version
from utils.context import ctx_aiohttp_session

if TYPE_CHECKING:
    from handler.metadata.igdb_handler import TwitchAuth


class IGDBInvalidCredentialsException(Exception):
    """Exception raised when IGDB credentials are invalid."""


async def auth_middleware(
    req: aiohttp.ClientRequest,
    handler: aiohttp.ClientHandlerType,
    *,
    twitch_auth: "TwitchAuth",
) -> aiohttp.ClientResponse:
    """IGDB API authentication mechanism.

    Reference: https://api-docs.igdb.com/#authentication
    """
    token = await twitch_auth.get_oauth_token()
    if not token:
        raise IGDBInvalidCredentialsException()
    req.headers.update(
        {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Client-ID": IGDB_CLIENT_ID,
        }
    )
    return await handler(req)


class IGDBService:
    """Service to interact with the IGDB API.

    Reference: https://api-docs.igdb.com/
    """

    def __init__(
        self,
        twitch_auth: "TwitchAuth",
        base_url: str | None = None,
    ) -> None:
        self.url = yarl.URL(base_url or "https://api.igdb.com/v4")
        self.twitch_auth = twitch_auth
        self.auth_middleware = partial(auth_middleware, twitch_auth=self.twitch_auth)

    async def _request(
        self,
        url: str,
        search_term: str | None = None,
        fields: Sequence[str] | None = None,
        where: str | None = None,
        limit: int | None = None,
        request_timeout: int = 120,
    ) -> list:
        aiohttp_session = ctx_aiohttp_session.get()

        content = ""
        if search_term:
            content += f'search "{unidecode(search_term)}"; '
        if fields:
            content += f"fields {','.join(fields)}; "
        if where:
            content += f"where {where}; "
        if limit is not None:
            content += f"limit {limit}; "
        content = content.strip()

        log.debug(
            "API request: URL=%s, Content=%s, Timeout=%s",
            url,
            content,
            request_timeout,
        )

        try:
            res = await aiohttp_session.post(
                url,
                data=content,
                headers={"user-agent": f"RomM/{get_version()}"},
                middlewares=(self.auth_middleware,),
                timeout=ClientTimeout(total=request_timeout),
            )
            res.raise_for_status()
            return await res.json()
        except aiohttp.ServerTimeoutError:
            # Retry the request once if it times out
            log.debug("Request to URL=%s timed out. Retrying...", url)
        except IGDBInvalidCredentialsException as exc:
            log.critical("IGDB Error: Invalid IGDB_CLIENT_ID or IGDB_CLIENT_SECRET")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Invalid IGDB credentials",
            ) from exc
        except aiohttp.ClientConnectionError as exc:
            log.critical("Connection error: can't connect to IGDB", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to IGDB, check your internet connection",
            ) from exc
        except aiohttp.ClientResponseError as exc:
            if exc.status == http.HTTPStatus.UNAUTHORIZED:
                # Refresh the token and retry if the auth token is invalid
                log.info("Twitch token invalid: fetching a new one...")
                await self.twitch_auth._update_twitch_token()
            elif exc.status == http.HTTPStatus.TOO_MANY_REQUESTS:
                # Retry after 2 seconds if rate limit hit
                await asyncio.sleep(2)
            else:
                # Log the error and return an empty list if the request fails with a different code
                log.error(exc)
                return []
        except json.JSONDecodeError as exc:
            log.error("Error decoding JSON response from IGDB: %s", exc)
            return []

        # Retry the request once if it times out
        try:
            log.debug(
                "API request: URL=%s, Content=%s, Timeout=%s",
                url,
                content,
                request_timeout,
            )
            res = await aiohttp_session.post(
                url,
                data=content,
                headers={"user-agent": f"RomM/{get_version()}"},
                middlewares=(self.auth_middleware,),
                timeout=ClientTimeout(total=request_timeout),
            )
            res.raise_for_status()
            return await res.json()
        except (aiohttp.ClientResponseError, aiohttp.ServerTimeoutError) as exc:
            if (
                isinstance(exc, aiohttp.ClientResponseError)
                and exc.status == http.HTTPStatus.UNAUTHORIZED
            ):
                return []

            log.error(exc)
            return []
        except json.JSONDecodeError as exc:
            log.error("Error decoding JSON response from IGDB: %s", exc)
            return []

    async def list_games(
        self,
        *,
        search_term: str | None = None,
        fields: Sequence[str] | None = None,
        where: str | None = None,
        limit: int | None = None,
    ) -> list[Game]:
        """Retrieve games.

        Reference: https://api-docs.igdb.com/#game
        """
        url = self.url.joinpath("games")
        return await self._request(
            str(url),
            search_term=search_term,
            fields=fields,
            where=where,
            limit=limit,
        )

    async def search(
        self,
        *,
        search_term: str | None = None,
        fields: Sequence[str] | None = None,
        where: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """Search for different entities.

        Reference: https://api-docs.igdb.com/#search
        """
        url = self.url.joinpath("search")
        return await self._request(
            str(url),
            search_term=search_term,
            fields=fields,
            where=where,
            limit=limit,
        )
