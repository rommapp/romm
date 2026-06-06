import asyncio

import pytest

from utils.rate_limiter import ConcurrencyLimiter, RateLimiter


def _record_sleeps(monkeypatch) -> list[float]:
    """Replace asyncio.sleep with a no-op that records requested delays."""
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    return sleeps


class TestRateLimiter:
    async def test_first_acquire_does_not_sleep(self, monkeypatch):
        sleeps = _record_sleeps(monkeypatch)
        limiter = RateLimiter(requests_per_second=4)

        await limiter.acquire()

        assert sleeps == []

    async def test_slots_advance_by_interval(self, monkeypatch):
        sleeps = _record_sleeps(monkeypatch)
        limiter = RateLimiter(requests_per_second=4)

        for _ in range(5):
            await limiter.acquire()

        # First grant is immediate; the next four are spaced one interval apart.
        assert len(sleeps) == 4
        for index, delay in enumerate(sleeps, start=1):
            assert delay == pytest.approx(index * 0.25, abs=0.05)

    async def test_concurrent_callers_are_spaced(self):
        rate = 50
        interval = 1 / rate
        count = 5
        limiter = RateLimiter(requests_per_second=rate)

        loop = asyncio.get_running_loop()
        start = loop.time()
        await asyncio.gather(*(limiter.acquire() for _ in range(count)))
        elapsed = loop.time() - start

        assert elapsed >= (count - 1) * interval
        assert elapsed < (count - 1) * interval + 0.5

    @pytest.mark.parametrize("rate", [0, -1, -0.5])
    def test_non_positive_rate_raises(self, rate):
        with pytest.raises(ValueError):
            RateLimiter(requests_per_second=rate)


class TestConcurrencyLimiter:
    @pytest.mark.parametrize("value", [0, -1])
    def test_non_positive_capacity_raises(self, value):
        with pytest.raises(ValueError):
            ConcurrencyLimiter(max_concurrency=value)

    async def test_acquire_release_tracks_in_flight(self):
        limiter = ConcurrencyLimiter(max_concurrency=2)

        await limiter.acquire()
        await limiter.acquire()
        assert limiter.in_flight == 2

        limiter.release()
        assert limiter.in_flight == 1

    async def test_context_manager_releases(self):
        limiter = ConcurrencyLimiter(max_concurrency=1)

        async with limiter:
            assert limiter.in_flight == 1
        assert limiter.in_flight == 0

    async def test_context_manager_releases_on_error(self):
        limiter = ConcurrencyLimiter(max_concurrency=1)

        with pytest.raises(RuntimeError):
            async with limiter:
                raise RuntimeError("boom")

        assert limiter.in_flight == 0

    async def test_acquire_blocks_until_slot_freed(self):
        limiter = ConcurrencyLimiter(max_concurrency=1)
        await limiter.acquire()

        waiter = asyncio.ensure_future(limiter.acquire())
        await asyncio.sleep(0)  # Let the waiter run and block.
        assert not waiter.done()

        limiter.release()
        await asyncio.wait_for(waiter, timeout=1)
        assert limiter.in_flight == 1

    async def test_set_max_concurrency_wakes_waiters(self):
        limiter = ConcurrencyLimiter(max_concurrency=1)
        await limiter.acquire()

        waiter = asyncio.ensure_future(limiter.acquire())
        await asyncio.sleep(0)
        assert not waiter.done()

        # Opening a second slot should release the blocked acquirer.
        limiter.set_max_concurrency(2)
        await asyncio.wait_for(waiter, timeout=1)
        assert limiter.in_flight == 2

    async def test_lowering_capacity_blocks_new_acquirers(self):
        limiter = ConcurrencyLimiter(max_concurrency=2)
        await limiter.acquire()
        limiter.set_max_concurrency(1)

        waiter = asyncio.ensure_future(limiter.acquire())
        await asyncio.sleep(0)
        # Already at the new cap, so the next acquirer must wait.
        assert not waiter.done()

        limiter.release()
        await asyncio.wait_for(waiter, timeout=1)
        assert limiter.in_flight == 1

    @pytest.mark.parametrize("value", [0, -1])
    def test_set_non_positive_capacity_raises(self, value):
        limiter = ConcurrencyLimiter(max_concurrency=1)
        with pytest.raises(ValueError):
            limiter.set_max_concurrency(value)
