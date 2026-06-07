from contextvars import ContextVar
from unittest.mock import AsyncMock

import aiohttp
import pytest
import pytest_asyncio

from adapters.services.screenscraper import SS_DEFAULT_MAX_THREADS
from utils.rate_limiter import ConcurrencyLimiter


@pytest.fixture(autouse=True)
def disable_metadata_rate_limiters(monkeypatch):
    """Neutralize the pre-emptive rate limiters during tests."""
    for module in (
        "adapters.services.igdb",
        "adapters.services.mobygames",
        "adapters.services.retroachievements",
        "adapters.services.screenscraper",
    ):
        mod = __import__(module, fromlist=["_rate_limiter"])
        monkeypatch.setattr(mod._rate_limiter, "acquire", AsyncMock())

    # Swap in a fresh instance of the concurrency limiter for each test
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
