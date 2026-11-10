"""Failure handling shared by the metadata providers' HTTP clients."""

import asyncio
import http
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Final

import aiohttp
from fastapi import HTTPException, status

from logger.logger import log

RATE_LIMIT_BACKOFF_SECONDS: Final[float] = 2
# Bounds a provider's Retry-After so one reply can't stall a request for long.
MAX_RETRY_AFTER_SECONDS: Final[float] = 60


def unavailable(provider: str) -> HTTPException:
    """The error a provider raises when it can't be reached."""
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Can't connect to {provider}, check your internet connection",
    )


def _retry_after_seconds(value: str) -> float | None:
    """Seconds to wait from a Retry-After header, in seconds or HTTP-date form."""
    try:
        seconds = float(value)
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        # A date already past means the provider is ready now.
        return max((when - datetime.now(UTC)).total_seconds(), 0)
    return seconds if seconds >= 0 else None


def _rate_limit_delay(
    exc: aiohttp.ClientResponseError, backoff: float, attempt: int
) -> float:
    """The provider's Retry-After when it sends one, else a doubling backoff."""
    retry_after = exc.headers.get("Retry-After") if exc.headers else None
    seconds = _retry_after_seconds(retry_after) if retry_after is not None else None
    if seconds is not None:
        return min(seconds, MAX_RETRY_AFTER_SECONDS)
    return backoff * 2.0 ** (attempt - 1)


async def send_with_retries[T](
    send: Callable[[], Awaitable[T]],
    *,
    provider: str,
    url: str,
    attempts: int = 2,
    rate_limit_attempts: int | None = None,
    backoff: float = RATE_LIMIT_BACKOFF_SECONDS,
    retry_on_status: (
        Callable[[aiohttp.ClientResponseError], Awaitable[bool]] | None
    ) = None,
) -> T:
    """Send a request, retrying a timeout or a 429 (after its Retry-After or a doubling backoff).

    Args:
        rate_limit_attempts: Attempts allowed when the latest reply is a 429,
            `attempts` by default; earlier timeouts count toward them.
        retry_on_status: Decides whether another error status earns a retry.

    Raises:
        HTTPException: A 503 when the provider can't be reached.
        TimeoutError: The last attempt timed out.
        aiohttp.ClientResponseError: An error status that earns no retry.
    """
    if rate_limit_attempts is None:
        rate_limit_attempts = attempts
    for attempt in range(1, max(attempts, rate_limit_attempts) + 1):
        try:
            return await send()
        # A `total` timeout is a bare TimeoutError, not aiohttp's ServerTimeoutError.
        except TimeoutError:
            if attempt >= attempts:
                raise
            log.debug("Request to URL=%s timed out. Retrying...", url)
        except aiohttp.ClientConnectionError as exc:
            log.critical(
                "Connection error: can't connect to %s", provider, exc_info=True
            )
            raise unavailable(provider) from exc
        except aiohttp.ClientResponseError as exc:
            if exc.status == http.HTTPStatus.TOO_MANY_REQUESTS:
                if attempt >= rate_limit_attempts:
                    raise
                delay = _rate_limit_delay(exc, backoff, attempt)
                log.warning("%s: rate limit hit, retrying after %ss", provider, delay)
                await asyncio.sleep(delay)
            elif (
                attempt >= attempts
                or retry_on_status is None
                or not await retry_on_status(exc)
            ):
                raise

    raise ValueError(f"attempts must be at least 1, got {attempts}")
