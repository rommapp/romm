from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.services.igdb import IGDBService


class TestIGDBServiceUnit:
    """Unit tests with mocked dependencies."""

    @pytest.fixture
    def service(self):
        """Create an IGDBService instance for testing."""
        return IGDBService(twitch_auth=MagicMock())

    @pytest.mark.asyncio
    async def test_request_acquires_rate_limiter(self, service, monkeypatch):
        """Test that the request reserves a rate-limiter slot before sending."""
        acquire_mock = AsyncMock()
        monkeypatch.setattr(
            "adapters.services.igdb._rate_limiter.acquire", acquire_mock
        )

        mock_session = AsyncMock()
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value=[{"id": 1}])
        mock_response.raise_for_status.return_value = None
        mock_session.post.return_value = mock_response

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.igdb.ctx_aiohttp_session", mock_context):
            result = await service._request("https://api.igdb.com/v4/games")

        acquire_mock.assert_awaited_once()
        assert result == [{"id": 1}]
