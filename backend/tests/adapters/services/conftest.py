from contextvars import ContextVar
from unittest.mock import AsyncMock

import aiohttp
import pytest
import pytest_asyncio

from adapters.services.screenscraper import SS_DEFAULT_MAX_THREADS
from utils.rate_limiter import ConcurrencyLimiter


@pytest.fixture(autouse=True)
def _disable_metadata_rate_limiters(monkeypatch):
    """Neutralize the pre-emptive rate limiters during tests.

    Each req/s-limited service spaces its requests via a module-level
    ``RateLimiter`` whose ``acquire`` sleeps to stay under the provider's cap.
    Letting it run would add real delays and inject extra ``asyncio.sleep`` calls
    that interfere with retry assertions, so we replace ``acquire`` with a no-op.
    """
    for module in (
        "adapters.services.igdb",
        "adapters.services.mobygames",
        "adapters.services.retroachievements",
    ):
        monkeypatch.setattr(f"{module}._rate_limiter.acquire", AsyncMock())

    # ScreenScraper uses a concurrency limiter whose capacity mutates at runtime
    # from `ssuser.maxthreads`. Swap in a fresh instance so each test starts from
    # the default allowance with a clean (per-loop) waiter queue.
    monkeypatch.setattr(
        "adapters.services.screenscraper._concurrency_limiter",
        ConcurrencyLimiter(SS_DEFAULT_MAX_THREADS),
    )


@pytest_asyncio.fixture
async def mock_ctx_aiohttp_session():
    """Create a real aiohttp session for integration tests."""
    session = aiohttp.ClientSession()
    ctx_aiohttp_session: ContextVar[aiohttp.ClientSession] = ContextVar(
        "aiohttp_session"
    )
    ctx_aiohttp_session.set(session)
    try:
        yield ctx_aiohttp_session
    finally:
        await session.close()
