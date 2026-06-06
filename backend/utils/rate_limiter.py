import asyncio


class RateLimiter:
    """Pre-emptive async rate limiter.

    Spaces grants so callers stay at or below ``requests_per_second``. Concurrent
    callers each reserve the next slot before awaiting, so they are evenly spaced
    instead of being released in a burst.
    """

    def __init__(self, requests_per_second: float) -> None:
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        self._min_interval = 1.0 / requests_per_second
        self._next_slot = 0.0

    async def acquire(self) -> None:
        # Reserving the slot is a read-then-write on _next_slot with no await
        # between, so it is atomic on the single-threaded loop and needs no lock.
        loop = asyncio.get_running_loop()
        now = loop.time()
        slot = max(now, self._next_slot)
        self._next_slot = slot + self._min_interval

        delay = slot - now
        if delay > 0:
            await asyncio.sleep(delay)
