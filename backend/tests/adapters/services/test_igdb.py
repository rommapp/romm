from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.services import igdb
from adapters.services.igdb import IGDBService


class TestIGDBServiceUnit:
    """Unit tests with mocked dependencies."""

    @pytest.fixture
    def service(self):
        """Create an IGDBService instance for testing."""
        return IGDBService(twitch_auth=MagicMock())

    @pytest.mark.asyncio
    async def test_request_acquires_rate_limiter(self, service):
        """Test that the request reserves a rate-limiter slot before sending."""
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value=[{"id": 1}])
        mock_response.raise_for_status.return_value = None

        # Record the order in which the rate limiter is acquired and the request is sent
        call_order: list[str] = []
        acquire_mock = cast(AsyncMock, igdb._rate_limiter.acquire)
        acquire_mock.side_effect = lambda *a, **k: call_order.append("acquire")

        async def record_post(*args, **kwargs):
            call_order.append("post")
            return mock_response

        mock_session = AsyncMock()
        mock_session.post.side_effect = record_post

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.igdb.ctx_aiohttp_session", mock_context):
            result = await service._request("https://api.igdb.com/v4/games")

        assert result == [{"id": 1}]
        # The rate-limiter slot must be reserved, and before the request is sent.
        acquire_mock.assert_awaited_once()
        mock_session.post.assert_awaited_once()
        assert call_order == [
            "acquire",
            "post",
        ], "rate limiter must be acquired before the POST is sent"
