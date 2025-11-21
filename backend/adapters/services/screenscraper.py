import asyncio
import base64
import http
import json
from typing import Final, cast

import aiohttp
import yarl
from aiohttp.client import ClientTimeout
from fastapi import HTTPException, status

from adapters.services.screenscraper_types import SSGame
from config import SCREENSCRAPER_PASSWORD, SCREENSCRAPER_USER
from logger.logger import log
from utils import get_version
from utils.context import ctx_aiohttp_session

SS_DEV_ID: Final = base64.b64decode("enVyZGkxNQ==").decode()
SS_DEV_PASSWORD: Final = base64.b64decode("eFRKd29PRmpPUUc=").decode()
LOGIN_ERROR_CHECK: Final = "Erreur de login"


async def auth_middleware(
    req: aiohttp.ClientRequest, handler: aiohttp.ClientHandlerType
) -> aiohttp.ClientResponse:
    """ScreenScraper API authentication mechanism."""
    req.url = req.url.update_query(
        {
            "devid": SS_DEV_ID,
            "devpassword": SS_DEV_PASSWORD,
            "output": "json",
            "softname": "romm",
            "ssid": SCREENSCRAPER_USER,
            "sspassword": SCREENSCRAPER_PASSWORD,
        },
    )
    return await handler(req)


class ScreenScraperService:
    """Service to interact with the ScreenScraper API.

    Reference: https://api.screenscraper.fr/webapi2.php
    """

    def __init__(
        self,
        base_url: str | None = None,
    ) -> None:
        self.url = yarl.URL(base_url or "https://api.screenscraper.fr/api2")

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
            res_text = await res.text()
            if LOGIN_ERROR_CHECK in res_text:
                log.error("Invalid ScreenScraper credentials")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid ScreenScraper credentials",
                )
            return await res.json()
        except aiohttp.ServerTimeoutError:
            # Retry the request once if it times out
            pass
        except aiohttp.ClientConnectionError as exc:
            log.critical(
                "Connection error: can't connect to ScreenScraper", exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to ScreenScraper, check your internet connection",
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
            res_text = await res.text()
            if LOGIN_ERROR_CHECK in res_text:
                log.error("Invalid ScreenScraper credentials")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid ScreenScraper credentials",
                )
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

    async def get_infra_info(self) -> dict:
        """Retrieve information about the infrastructure.

        Reference: https://api.screenscraper.fr/webapi2.php#infraInfos
        """
        url = self.url.joinpath("ssinfraInfos.php")
        return await self._request(str(url))

    async def get_game_info(
        self,
        *,
        crc: str | None = None,
        md5: str | None = None,
        sha1: str | None = None,
        system_id: int | None = None,
        rom_type: str | None = None,
        rom_name: str | None = None,
        rom_size_bytes: int | None = None,
        serial_number: str | None = None,
        game_id: int | None = None,
    ) -> SSGame | None:
        """Retrieve information about a game.

        Reference: https://api.screenscraper.fr/webapi2.php#jeuInfos
        """
        params: dict[str, list[str]] = {}
        if crc:
            params["crc"] = [crc]
        if md5:
            params["md5"] = [md5]
        if sha1:
            params["sha1"] = [sha1]
        if system_id is not None:
            params["systemeid"] = [str(system_id)]
        if rom_type:
            params["romtype"] = [rom_type]
        if rom_name:
            params["romnom"] = [rom_name]
        if rom_size_bytes is not None:
            params["romtaille"] = [str(rom_size_bytes)]
        if serial_number:
            params["serialnum"] = [serial_number]
        if game_id is not None:
            params["gameid"] = [str(game_id)]

        url = self.url.joinpath("jeuInfos.php").with_query(**params)
        response = await self._request(str(url))
        data = response.get("response", {}).get("jeu", {})
        if not data:
            return None
        return cast(SSGame, data)

    async def search_games(
        self,
        *,
        term: str,
        system_id: int | None = None,
    ) -> list[SSGame]:
        """Search games by name. Returns games sorted by relevance (limited to 30 results).

        Reference: https://api.screenscraper.fr/webapi2.php#jeuRecherche
        """
        params: dict[str, list[str]] = {"recherche": [term]}
        if system_id is not None:
            params["systemeid"] = [str(system_id)]

        url = self.url.joinpath("jeuRecherche.php").with_query(**params)
        response = await self._request(str(url))
        data = response.get("response", {}).get("jeux", [])
        # If no roms are returned, "jeux" is a list with an empty dict.
        if len(data) == 1 and not data[0]:
            data = []
        return cast(list[SSGame], data)
