import asyncio
from collections import deque


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


class ConcurrencyLimiter:
    """Caps the number of in-flight operations, with a runtime-adjustable capacity.

    Unlike :class:`RateLimiter`, which spaces out *when* requests start, this
    bounds how many run *simultaneously*. It suits APIs that enforce a per-account
    thread/connection cap (e.g. ScreenScraper) rather than a call rate: because a
    slot is held for the whole request, slow responses can never cause overlapping
    requests to exceed the cap.

    The capacity can be raised or lowered at runtime via
    :meth:`set_max_concurrency` -- for instance once an API response reveals the
    account's allowance. Use it as an async context manager so the slot is always
    released, even if the wrapped request raises::

        async with limiter:
            await do_request()

    The implementation is loop-agnostic: waiter futures are created against the
    running loop on acquisition, so a single shared instance works across the
    distinct event loops used by, e.g., the test suite.
    """

    def __init__(self, max_concurrency: int) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        self._max_concurrency = max_concurrency
        self._in_flight = 0
        self._waiters: deque[asyncio.Future[None]] = deque()

    @property
    def max_concurrency(self) -> int:
        return self._max_concurrency

    @property
    def in_flight(self) -> int:
        return self._in_flight

    def set_max_concurrency(self, max_concurrency: int) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        previous = self._max_concurrency
        self._max_concurrency = max_concurrency
        # Wake one waiter per newly opened slot; each re-checks capacity itself.
        for _ in range(max(0, max_concurrency - previous)):
            self._wake_next()

    async def acquire(self) -> None:
        # Re-check on every wake-up: another coroutine may have taken the slot,
        # or the capacity may have been lowered while we waited.
        while self._in_flight >= self._max_concurrency:
            loop = asyncio.get_running_loop()
            waiter = loop.create_future()
            self._waiters.append(waiter)
            try:
                try:
                    await waiter
                finally:
                    self._waiters.remove(waiter)
            except asyncio.CancelledError:
                # We were granted a slot but cancelled before using it; pass the
                # grant on so a waiting peer is not stranded.
                if not waiter.cancelled():
                    self._wake_next()
                raise
        self._in_flight += 1

    def release(self) -> None:
        if self._in_flight > 0:
            self._in_flight -= 1
        self._wake_next()

    def _wake_next(self) -> None:
        for waiter in self._waiters:
            if not waiter.done():
                waiter.set_result(None)
                return

    async def __aenter__(self) -> "ConcurrencyLimiter":
        await self.acquire()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self.release()
