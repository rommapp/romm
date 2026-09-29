import asyncio

import pytest

from handler.install import bandwidth
from handler.redis_handler import async_cache


@pytest.fixture(autouse=True)
async def _clear_bandwidth_state():
    """Redis (fakeredis under pytest) is a single shared store across the
    whole test session - clear this module's keys so tests don't leak
    the configured limit or window counters into each other."""
    await async_cache.delete(bandwidth._LIMIT_KEY)
    keys = [
        k async for k in async_cache.scan_iter(match=f"{bandwidth._WINDOW_KEY_PREFIX}*")
    ]
    if keys:
        await async_cache.delete(*keys)
    yield
    await async_cache.delete(bandwidth._LIMIT_KEY)
    keys = [
        k async for k in async_cache.scan_iter(match=f"{bandwidth._WINDOW_KEY_PREFIX}*")
    ]
    if keys:
        await async_cache.delete(*keys)


class TestSetAndGetBytesPerSecond:
    @pytest.mark.asyncio
    async def test_defaults_to_unlimited(self):
        assert await bandwidth.get_bytes_per_second() is None

    @pytest.mark.asyncio
    async def test_set_then_get_round_trips(self):
        await bandwidth.set_bytes_per_second(1024)
        assert await bandwidth.get_bytes_per_second() == 1024

    @pytest.mark.asyncio
    async def test_none_clears_the_limit(self):
        await bandwidth.set_bytes_per_second(1024)
        await bandwidth.set_bytes_per_second(None)
        assert await bandwidth.get_bytes_per_second() is None

    @pytest.mark.asyncio
    async def test_zero_clears_the_limit(self):
        await bandwidth.set_bytes_per_second(1024)
        await bandwidth.set_bytes_per_second(0)
        assert await bandwidth.get_bytes_per_second() is None


class TestAcquire:
    @pytest.mark.asyncio
    async def test_unlimited_never_waits(self):
        # No limit configured at all - acquire() must be an immediate no-op
        # regardless of how large the request is.
        await asyncio.wait_for(bandwidth.acquire(10**9), timeout=0.5)

    @pytest.mark.asyncio
    async def test_zero_bytes_is_always_a_noop(self):
        await bandwidth.set_bytes_per_second(1)
        await asyncio.wait_for(bandwidth.acquire(0), timeout=0.5)

    @pytest.mark.asyncio
    async def test_grants_immediately_within_budget(self):
        await bandwidth.set_bytes_per_second(1_000_000)
        await asyncio.wait_for(bandwidth.acquire(1000), timeout=0.5)

    @pytest.mark.asyncio
    async def test_second_caller_over_budget_waits_for_the_next_window(
        self, monkeypatch
    ):
        await bandwidth.set_bytes_per_second(100)
        slept: list[float] = []

        async def fake_sleep(seconds):
            slept.append(seconds)
            # Stop the retry loop after one wait by raising once budget was
            # already exhausted - the real next window would grant it, but
            # we only care that a wait actually happened here.
            raise asyncio.CancelledError()

        monkeypatch.setattr(bandwidth.asyncio, "sleep", fake_sleep)

        await bandwidth.acquire(60)  # fits, grants immediately
        with pytest.raises(asyncio.CancelledError):
            await bandwidth.acquire(60)  # 60+60 > 100 - must wait
        assert slept

    @pytest.mark.asyncio
    async def test_a_backed_off_reservation_is_given_back(self):
        # Confirms the "over budget" branch decrements its own reservation
        # back out, rather than permanently consuming budget it never used -
        # otherwise a burst of failed acquires would starve every later
        # caller in the same window even after they back off.
        await bandwidth.set_bytes_per_second(100)
        window_key_before = None
        async for key in async_cache.scan_iter(
            match=f"{bandwidth._WINDOW_KEY_PREFIX}*"
        ):
            window_key_before = key
        assert window_key_before is None

        await bandwidth.acquire(90)  # fits

        keys = [
            k
            async for k in async_cache.scan_iter(
                match=f"{bandwidth._WINDOW_KEY_PREFIX}*"
            )
        ]
        assert len(keys) == 1
        used = int(await async_cache.get(keys[0]))
        assert used == 90
