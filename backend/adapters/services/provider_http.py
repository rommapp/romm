"""Failure handling shared by the metadata providers' HTTP clients."""

import asyncio
import http
from collections.abc import Awaitable, Callable
from typing import Final

import aiohttp
from fastapi import HTTPException, status

from logger.logger import log

RATE_LIMIT_BACKOFF_SECONDS: Final[float] = 2


def unavailable(provider: str) -> HTTPException:
    """The error a provider raises when it can't be reached."""
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Can't connect to {provider}, check your internet connection",
    )


async def send_with_retries[T](
    send: Callable[[], Awaitable[T]],
    *,
    provider: str,
    url: str,
    attempts: int = 2,
    backoff: float = RATE_LIMIT_BACKOFF_SECONDS,
    retry_on_status: (
        Callable[[aiohttp.ClientResponseError], Awaitable[bool]] | None
    ) = None,
) -> T:
    """Send a request, retrying a timeout or a 429 while attempts remain.

    Args:
        retry_on_status: Decides whether another error status earns a retry.

    Raises:
        HTTPException: A 503 when the provider can't be reached.
        TimeoutError: The last attempt timed out.
        aiohttp.ClientResponseError: An error status that earns no retry.
    """
    for attempt in range(1, attempts + 1):
        is_last = attempt == attempts
        try:
            return await send()
        # A `total` timeout is a bare TimeoutError, not aiohttp's ServerTimeoutError.
        except TimeoutError:
            if is_last:
                raise
            log.debug("Request to URL=%s timed out. Retrying...", url)
        except aiohttp.ClientConnectionError as exc:
            log.critical(
                "Connection error: can't connect to %s", provider, exc_info=True
            )
            raise unavailable(provider) from exc
        except aiohttp.ClientResponseError as exc:
            if is_last:
                raise
            if exc.status == http.HTTPStatus.TOO_MANY_REQUESTS:
                log.warning("%s: rate limit hit, retrying after %ss", provider, backoff)
                await asyncio.sleep(backoff)
            elif retry_on_status is None or not await retry_on_status(exc):
                raise

    raise ValueError(f"attempts must be at least 1, got {attempts}")
