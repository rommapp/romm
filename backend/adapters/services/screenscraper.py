import asyncio
import http
import json
import re
from typing import Final, cast

import aiohttp
import yarl
from aiohttp.client import ClientTimeout
from fastapi import HTTPException, status

from adapters.services.screenscraper_types import SSGame
from config import (
    SCREENSCRAPER_DEV_ID,
    SCREENSCRAPER_DEV_PASSWORD,
    SCREENSCRAPER_PASSWORD,
    SCREENSCRAPER_USER,
)
from logger.logger import log
from utils import get_version
from utils.context import ctx_aiohttp_session
from utils.rate_limiter import ConcurrencyLimiter

LOGIN_ERROR_CHECK: Final = "Erreur de login"

# ScreenScraper occasionally returns malformed JSON with unescaped backslashes in
# text fields (e.g. game synopses), which the strict parser rejects with
# "Invalid \escape" and discards the whole response. Match any backslash that is
# not part of a valid JSON escape so we can repair those before parsing.
_INVALID_ESCAPE_RE: Final = re.compile(r'\\(?!["\\/bfnrtu])')


def _loads_lenient(text: str) -> dict:
    """Parse a ScreenScraper JSON payload, repairing invalid escapes on failure.

    A single unescaped backslash would otherwise sink an entire response (and thus
    the match), so on a decode error we double any backslash that isn't a valid
    JSON escape and try once more.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(_INVALID_ESCAPE_RE.sub(r"\\\\", text))


# ScreenScraper enforces a per-account *thread* (concurrency) cap rather than a
# request rate. Because a request can take several seconds, spacing out request
# starts is not enough, as overlapping requests would exceed the cap and get
# rejected. We instead bound simultaneous in-flight requests.
SS_DEFAULT_MAX_THREADS: Final[int] = 1
_concurrency_limiter = ConcurrencyLimiter(SS_DEFAULT_MAX_THREADS)

# ScreenScraper enforces a *daily* request quota (HTTP 430/431) separate from
# the transient rate limit (HTTP 429). The daily quota only resets the next day,
# so once it's hit there's nothing to wait for within a scan. Trip a breaker on
# the first daily-quota error so the remaining requests short-circuit instead of
# hammering a dead quota. reset_daily_quota() clears it at the start of a scan.
_daily_quota_exhausted = False


def reset_daily_quota() -> None:
    """Clear the daily-quota breaker so the next scan re-evaluates the quota."""
    global _daily_quota_exhausted
    _daily_quota_exhausted = False


def is_daily_quota_exhausted() -> bool:
    """Whether the ScreenScraper daily quota has been exhausted this scan."""
    return _daily_quota_exhausted


def _trip_daily_quota(reason: str) -> None:
    """Trip the daily-quota breaker, logging a single clear notice the first time."""
    global _daily_quota_exhausted
    if not _daily_quota_exhausted:
        log.warning(
            "ScreenScraper %s; skipping ScreenScraper for the rest of this scan "
            "(quota resets tomorrow)",
            reason,
        )
    _daily_quota_exhausted = True


def _update_thread_allowance(response: dict) -> None:
    """Raise (or lower) the concurrency cap to the account's advertised threads.

    ScreenScraper reports the per-account thread allowance in
    ``response.ssuser.maxthreads`` (higher for contributors/donors).
    """
    try:
        max_threads = int(response["response"]["ssuser"]["maxthreads"])
    except (AttributeError, KeyError, TypeError, ValueError):
        return

    if max_threads < 1 or max_threads == _concurrency_limiter.max_concurrency:
        return

    log.info("ScreenScraper: setting thread allowance to %d", max_threads)
    _concurrency_limiter.set_max_concurrency(max_threads)


async def auth_middleware(
    req: aiohttp.ClientRequest, handler: aiohttp.ClientHandlerType
) -> aiohttp.ClientResponse:
    """ScreenScraper API authentication mechanism."""
    req.url = req.url.update_query(
        {
            "devid": SCREENSCRAPER_DEV_ID or "",
            "devpassword": SCREENSCRAPER_DEV_PASSWORD or "",
            "output": "json",
            "softname": "romm",
            "ssid": SCREENSCRAPER_USER or "",
            "sspassword": SCREENSCRAPER_PASSWORD or "",
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
        # Daily quota already exhausted earlier in this scan: skip the request but
        # still raise the quota error so callers (e.g. manual search) surface a
        # clear message. The scan loop catches this and falls back to the other
        # providers instead of hitting a dead quota for every remaining ROM.
        if _daily_quota_exhausted:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="ScreenScraper daily quota exhausted. Try again tomorrow.",
            )

        aiohttp_session = ctx_aiohttp_session.get()
        log.debug(
            "API request: URL=%s, Timeout=%s",
            url,
            request_timeout,
        )
        try:
            async with _concurrency_limiter:
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
                data = await res.json(loads=_loads_lenient)
            _update_thread_allowance(data)
            return data
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
                log.warning("ScreenScraper: rate limit hit, retrying after 2s")
                await asyncio.sleep(2)
            elif err.status == 426:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="ScreenScraper has blacklisted this application version. Please update RomM.",
                ) from err
            elif err.status == 430:
                _trip_daily_quota("daily scrape quota exhausted")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="ScreenScraper daily scrape quota exhausted. Try again tomorrow.",
                ) from err
            elif err.status == 431:
                _trip_daily_quota("daily unrecognized-ROM quota exhausted")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="ScreenScraper daily unrecognized-ROM quota exhausted. Try again tomorrow.",
                ) from err
            elif err.status == 423:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="ScreenScraper API is currently offline.",
                ) from err
            elif err.status == http.HTTPStatus.UNAUTHORIZED:
                log.warning(
                    "ScreenScraper API is temporarily unavailable (server CPU >60%)"
                )
                return {}
            else:
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
            async with _concurrency_limiter:
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
                data = await res.json(loads=_loads_lenient)
            _update_thread_allowance(data)
            return data
        except (aiohttp.ClientResponseError, aiohttp.ServerTimeoutError) as err:
            if isinstance(err, aiohttp.ClientResponseError):
                if err.status == http.HTTPStatus.UNAUTHORIZED:
                    log.warning(
                        "ScreenScraper API is temporarily unavailable (server CPU >60%)"
                    )
                    return {}
                elif err.status == 426:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="ScreenScraper has blacklisted this application version. Please update RomM.",
                    ) from err
                elif err.status == 430:
                    _trip_daily_quota("daily scrape quota exhausted")
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="ScreenScraper daily scrape quota exhausted. Try again tomorrow.",
                    ) from err
                elif err.status == 431:
                    _trip_daily_quota("daily unrecognized-ROM quota exhausted")
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="ScreenScraper daily unrecognized-ROM quota exhausted. Try again tomorrow.",
                    ) from err
                elif err.status == 423:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="ScreenScraper API is currently offline.",
                    ) from err

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
