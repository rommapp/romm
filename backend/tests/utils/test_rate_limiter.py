import asyncio

import pytest

from utils.rate_limiter import RateLimiter


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
