import asyncio
import http
import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, fields
from math import isclose
from typing import Final, cast
from urllib.parse import urlparse

import aiohttp
import yarl
from aiohttp.client import ClientTimeout
from fastapi import HTTPException, status

from adapters.services.screenscraper_types import SSGame, SSUser
from config import (
    SCAN_WORKERS,
    SCREENSCRAPER_DEV_ID,
    SCREENSCRAPER_DEV_PASSWORD,
    SCREENSCRAPER_PASSWORD,
    SCREENSCRAPER_USER,
)
from logger.logger import log
from utils import get_version
from utils.context import ctx_aiohttp_session
from utils.rate_limiter import ConcurrencyLimiter, RateLimiter

LOGIN_ERROR_CHECK: Final = "Erreur de login"

# ScreenScraper occasionally returns malformed JSON with unescaped backslashes in
# text fields (e.g. game synopses), which the strict parser rejects with
# "Invalid \escape" and discards the whole response. Match any backslash that is
# not part of a valid JSON escape so we can repair those before parsing.
_INVALID_ESCAPE_RE: Final = re.compile(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})')


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


# ScreenScraper enforces a per-account *thread* (concurrency) cap. Because a
# request can take several seconds, spacing out request starts is not enough, as
# overlapping requests would exceed the cap and get rejected. We instead bound
# simultaneous in-flight requests.
SS_DEFAULT_MAX_THREADS: Final[int] = 1
_concurrency_limiter = ConcurrencyLimiter(SS_DEFAULT_MAX_THREADS)

# On top of the thread cap, the account carries a per-minute budget. Responses
# can be fast enough (name searches average well under a second) to blow through
# it without ever exceeding the thread cap, so requests are paced as well as
# bounded, at whatever the account reports.
SS_UNPACED_REQUESTS_PER_SECOND: Final[float] = 1_000.0
_rate_limiter = RateLimiter(SS_UNPACED_REQUESTS_PER_SECOND)

# How close to either daily allowance the account has to be before we warn.
SS_LOW_QUOTA_FRACTION: Final[float] = 0.1

# Media downloads are served at the account's advertised speed, so their timeout
# is derived from how long a large file (a manual, a video) takes at that speed,
# bounded so a throttled account gets room to finish while a stalled download
# still gives up.
SS_DEFAULT_MEDIA_TIMEOUT: Final[int] = 120
SS_MAX_MEDIA_TIMEOUT: Final[int] = 600
SS_MEDIA_TIMEOUT_BUDGET_BYTES: Final[int] = 8 * 1024 * 1024


class ScreenScraperRateLimitError(HTTPException):
    """Raised when a request is refused for exceeding the per-minute rate twice.

    Kept distinct from the daily-quota 429 because this limit clears on its own
    within the minute: the scan carries on, but the ROM it was fetching has to be
    reported as skipped rather than saved with no ScreenScraper data.
    """

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="ScreenScraper rate limit exceeded, too many requests per minute.",
        )


@dataclass(frozen=True)
class SSAccountLimits:
    """The per-account allowances ScreenScraper reports on every response."""

    max_threads: int | None = None
    max_requests_per_minute: int | None = None
    max_requests_per_day: int | None = None
    requests_today: int | None = None
    max_ko_requests_per_day: int | None = None
    ko_requests_today: int | None = None
    max_download_speed_kbps: int | None = None

    @property
    def remaining_requests(self) -> int | None:
        if self.max_requests_per_day is None or self.requests_today is None:
            return None
        return max(0, self.max_requests_per_day - self.requests_today)

    @property
    def remaining_ko_requests(self) -> int | None:
        if self.max_ko_requests_per_day is None or self.ko_requests_today is None:
            return None
        return max(0, self.max_ko_requests_per_day - self.ko_requests_today)

    def describe(self) -> str:
        parts = []
        if self.remaining_requests is not None:
            parts.append(
                f"{self.requests_today}/{self.max_requests_per_day} daily requests "
                f"used ({self.remaining_requests} left)"
            )
        if self.remaining_ko_requests is not None:
            parts.append(
                f"{self.ko_requests_today}/{self.max_ko_requests_per_day} "
                f"unrecognized-ROM requests used ({self.remaining_ko_requests} left)"
            )

        if not parts:
            return "This account reports no quota information"

        return f"ScreenScraper quota: {', '.join(parts)}"


@dataclass
class _ScanState:
    """What ScreenScraper teaches us over the course of one scan.

    Process-wide rather than per-service: every caller shares the one account,
    and media downloads go through the limiters without a service at all.
    """

    account_limits: SSAccountLimits | None = None
    logged_worker_advisory: bool = False
    logged_low_quota_warning: bool = False

    # ScreenScraper enforces a *daily* request quota (HTTP 430/431) separate from
    # the transient rate limit (HTTP 429). The daily quota only resets the next
    # day, so once it's hit there's nothing to wait for within a scan. Trip a
    # breaker on the first daily-quota error so the remaining requests
    # short-circuit instead of hammering a dead quota.
    daily_quota_exhausted: bool = False

    def reset(self) -> None:
        for f in fields(self):
            setattr(self, f.name, f.default)


_state = _ScanState()


def reset_daily_quota() -> None:
    """Clear the daily-quota breaker so the next scan re-evaluates the quota."""
    _state.daily_quota_exhausted = False


def is_daily_quota_exhausted() -> bool:
    """Whether the ScreenScraper daily quota has been exhausted this scan."""
    return _state.daily_quota_exhausted


def _trip_daily_quota(reason: str) -> None:
    """Trip the daily-quota breaker, logging a single clear notice the first time."""
    if not _state.daily_quota_exhausted:
        log.warning(
            "ScreenScraper %s; skipping ScreenScraper for the rest of this scan "
            "(quotas reset at midnight CET)",
            reason,
        )
    _state.daily_quota_exhausted = True


def reset_scan_state() -> None:
    """Clear the per-scan ScreenScraper state at the start of a scan.

    The daily counters reset overnight, so stale limits are dropped rather than
    reported as this scan's; the one-shot advisories become due again.

    Pacing goes back to the defaults with them. Priming re-reads the account
    moments later, and should that fail, the one-thread default is safe for
    whatever account the credentials now name, whereas the previous scan's
    allowance may be more than this one is entitled to.
    """
    _state.reset()
    _concurrency_limiter.set_max_concurrency(SS_DEFAULT_MAX_THREADS)
    _rate_limiter.set_requests_per_second(SS_UNPACED_REQUESTS_PER_SECOND)


def get_account_limits() -> SSAccountLimits | None:
    """The account allowances read from the most recent response, if any."""
    return _state.account_limits


def _parse_int(value: object, *, minimum: int = 0) -> int | None:
    """Read one of the account's numeric fields, ignoring absent or junk values."""
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return None

    return parsed if parsed >= minimum else None


def _read_account_limits(ssuser: SSUser) -> SSAccountLimits:
    return SSAccountLimits(
        max_threads=_parse_int(ssuser.get("maxthreads"), minimum=1),
        max_requests_per_minute=_parse_int(ssuser.get("maxrequestspermin"), minimum=1),
        max_requests_per_day=_parse_int(ssuser.get("maxrequestsperday"), minimum=1),
        requests_today=_parse_int(ssuser.get("requeststoday")),
        max_ko_requests_per_day=_parse_int(
            ssuser.get("maxrequestskoperday"), minimum=1
        ),
        ko_requests_today=_parse_int(ssuser.get("requestskotoday")),
        max_download_speed_kbps=_parse_int(ssuser.get("maxdownloadspeed"), minimum=1),
    )


def _apply_thread_allowance(max_threads: int | None) -> None:
    """Raise (or lower) the concurrency cap to the account's advertised threads.

    Contributors and donors get more than the single thread a free account has.
    """
    if max_threads is None or max_threads == _concurrency_limiter.max_concurrency:
        return

    log.info("ScreenScraper: setting thread allowance to %d", max_threads)
    _concurrency_limiter.set_max_concurrency(max_threads)


def _apply_request_rate(limits: SSAccountLimits) -> None:
    """Pace requests against the account's per-minute budget.

    ScreenScraper's FAQ still gives the budget as ``threads x 50``, but the API
    was changed without the documentation following it, confirmed by
    ScreenScraper. ``maxrequestspermin`` carries the real figure, which on
    current accounts is ``1024 x (threads + 1)``, so the reported value is what
    we pace against rather than the formula.
    """
    per_minute = limits.max_requests_per_minute
    if not per_minute:
        return

    per_second = per_minute / 60
    if isclose(per_second, _rate_limiter.requests_per_second):
        return

    log.info("ScreenScraper: pacing requests at %d per minute", per_minute)
    _rate_limiter.set_requests_per_second(per_second)


def _log_worker_advisory(max_threads: int | None) -> None:
    """Flag a SCAN_WORKERS value that under- or over-uses the account.

    SCAN_WORKERS bounds how many ROMs are scanned at once, and so bounds how many
    ScreenScraper requests can ever be in flight.
    """
    if _state.logged_worker_advisory or max_threads is None:
        return

    _state.logged_worker_advisory = True

    if SCAN_WORKERS < max_threads:
        log.info(
            "ScreenScraper: this account allows %d simultaneous requests but "
            "SCAN_WORKERS is %d, so scanning is slower than it could be",
            max_threads,
            SCAN_WORKERS,
        )
    elif SCAN_WORKERS > max_threads:
        log.info(
            "ScreenScraper: SCAN_WORKERS is %d but this account allows %d "
            "simultaneous requests, so the extra workers will queue",
            SCAN_WORKERS,
            max_threads,
        )


def _warn_on_low_quota(limits: SSAccountLimits) -> None:
    """Warn before a daily allowance runs out, rather than after it is refused."""
    if _state.logged_low_quota_warning:
        return

    for remaining, allowance, label in (
        (limits.remaining_requests, limits.max_requests_per_day, "requests"),
        (
            limits.remaining_ko_requests,
            limits.max_ko_requests_per_day,
            "unrecognized-ROM requests",
        ),
    ):
        if remaining is None or allowance is None:
            continue

        if remaining <= allowance * SS_LOW_QUOTA_FRACTION:
            log.warning(
                "ScreenScraper: only %d of %d daily %s left, "
                "the quota resets at midnight CET",
                remaining,
                allowance,
                label,
            )
            _state.logged_low_quota_warning = True
            return


def _update_account_limits(response: dict) -> None:
    """Read the account allowances ScreenScraper attaches to every response.

    They govern how fast we may scrape (threads and requests per minute), how
    much of the daily quota is left, and how slowly media will download.
    """
    payload = response.get("response")
    if not isinstance(payload, dict):
        return

    ssuser = payload.get("ssuser")
    if not isinstance(ssuser, dict):
        return

    limits = _read_account_limits(cast(SSUser, ssuser))
    _state.account_limits = limits

    _apply_thread_allowance(limits.max_threads)
    _apply_request_rate(limits)
    _log_worker_advisory(limits.max_threads)
    _warn_on_low_quota(limits)


def is_screenscraper_url(url: str | None) -> bool:
    """True only if the URL's hostname is screenscraper.fr or a subdomain.

    Substring matching would let an attacker-controlled host like
    screenscraper.fr.evil.example pass as ScreenScraper's.
    """
    if not url:
        return False

    try:
        host = urlparse(url).hostname
    except ValueError:
        return False

    if not host:
        return False

    return host.lower() == "screenscraper.fr" or host.lower().endswith(
        ".screenscraper.fr"
    )


def media_download_timeout() -> int:
    """How long a media download may take at the account's advertised speed."""
    limits = _state.account_limits
    speed_kbps = limits.max_download_speed_kbps if limits else None
    if not speed_kbps:
        return SS_DEFAULT_MEDIA_TIMEOUT

    # Kb/s per thread per ScreenScraper's FAQ, and a download holds one thread,
    # so a free account's 128 gets minutes for a large manual while a
    # contributor's 40 Mb/s stays at the floor.
    seconds = SS_MEDIA_TIMEOUT_BUDGET_BYTES * 8 / (speed_kbps * 1000)
    return int(min(SS_MAX_MEDIA_TIMEOUT, max(SS_DEFAULT_MEDIA_TIMEOUT, seconds)))


@asynccontextmanager
async def media_download_slot(url: str) -> AsyncIterator[int]:
    """Hold a ScreenScraper request slot for a media download, yielding its timeout.

    Cover art, screenshots, manuals and the rest are served by ScreenScraper and
    count against the same thread and per-minute allowances as API calls, so they
    go through the same limiters. Other providers pass straight through.
    """
    if not is_screenscraper_url(url):
        yield SS_DEFAULT_MEDIA_TIMEOUT
        return

    async with _concurrency_limiter:
        await _rate_limiter.acquire()
        yield media_download_timeout()


async def prime_account_limits() -> SSAccountLimits | None:
    """Read the account's allowances before a scan starts.

    They ride along on every response, so waiting for the first scan request
    means the first ROMs are scraped one at a time on the default single thread.
    ssuserInfos.php reports them up front for free: unlike the scraping
    endpoints it does not consume the daily quota.

    Best effort. A scan must still run when ScreenScraper cannot be reached.
    """
    if not (SCREENSCRAPER_USER and SCREENSCRAPER_PASSWORD):
        return None

    try:
        await ScreenScraperService().get_user_info()
    except HTTPException as exc:
        log.warning("ScreenScraper: could not read the account limits (%s)", exc.detail)
    except (TimeoutError, aiohttp.ClientError) as exc:
        log.warning("ScreenScraper: could not read the account limits (%s)", exc)

    return _state.account_limits


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
        if _state.daily_quota_exhausted:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="ScreenScraper daily quota exhausted. It resets at midnight CET.",
            )

        aiohttp_session = ctx_aiohttp_session.get()
        log.debug(
            "API request: URL=%s, Timeout=%s",
            url,
            request_timeout,
        )
        try:
            async with _concurrency_limiter:
                await _rate_limiter.acquire()
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
            _update_account_limits(data)
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
                    detail="ScreenScraper daily scrape quota exhausted. It resets at midnight CET.",
                ) from err
            elif err.status == 431:
                _trip_daily_quota("daily unrecognized-ROM quota exhausted")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="ScreenScraper daily unrecognized-ROM quota exhausted. It resets at midnight CET.",
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
                await _rate_limiter.acquire()
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
            _update_account_limits(data)
            return data
        except (aiohttp.ClientResponseError, aiohttp.ServerTimeoutError) as err:
            if isinstance(err, aiohttp.ClientResponseError):
                if err.status == http.HTTPStatus.TOO_MANY_REQUESTS:
                    # Refused twice in a row: the pacing is behind the account's
                    # per-minute budget. Surface it so the ROM is reported as
                    # skipped instead of quietly saved without our metadata.
                    raise ScreenScraperRateLimitError() from err
                elif err.status == http.HTTPStatus.UNAUTHORIZED:
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
                        detail="ScreenScraper daily scrape quota exhausted. It resets at midnight CET.",
                    ) from err
                elif err.status == 431:
                    _trip_daily_quota("daily unrecognized-ROM quota exhausted")
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="ScreenScraper daily unrecognized-ROM quota exhausted. It resets at midnight CET.",
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

    async def get_user_info(self) -> dict:
        """Retrieve the account's allowances and quota counters.

        Reference: https://api.screenscraper.fr/webapi2.php#ssuserInfos
        """
        url = self.url.joinpath("ssuserInfos.php")
        return await self._request(str(url))

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
