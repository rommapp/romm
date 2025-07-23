from contextvars import ContextVar

import aiohttp
import pytest_asyncio


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
