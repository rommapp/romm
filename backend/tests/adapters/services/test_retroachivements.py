from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
import yarl
from fastapi import HTTPException, status

from adapters.services.retroachievements import (
    RetroAchievementsService,
    auth_middleware,
)

INVALID_GAME_ID = 999999


class TestAuthMiddleware:
    @patch("adapters.services.retroachievements.RETROACHIEVEMENTS_API_KEY", "test_key")
    @pytest.mark.asyncio
    async def test_auth_middleware_adds_api_key(self):
        """Test that auth middleware adds API key to request URL."""
        # Create a real request-like object
        mock_request = MagicMock()
        mock_request.url = yarl.URL("https://retroachievements.org/API")

        mock_handler = AsyncMock()
        mock_response = MagicMock()
        mock_handler.return_value = mock_response

        result = await auth_middleware(mock_request, mock_handler)

        # Check that the URL now contains the API key
        expected_url = yarl.URL("https://retroachievements.org/API").with_query(
            y="test_key"
        )
        assert mock_request.url == expected_url
        mock_handler.assert_called_once_with(mock_request)
        assert result == mock_response


class TestRetroAchievementsServiceUnit:
    """Unit tests with mocked dependencies."""

    @pytest.fixture
    def service(self):
        """Create a RetroAchievementsService instance for testing."""
        return RetroAchievementsService()

    @pytest.fixture
    def service_custom_url(self):
        """Create a RetroAchievementsService instance with custom URL."""
        return RetroAchievementsService("https://custom.api.com")

    def test_init_default_url(self, service):
        """Test service initialization with default URL."""
        assert str(service.url) == "https://retroachievements.org/API"

    def test_init_custom_url(self, service_custom_url):
        """Test service initialization with custom URL."""
        assert str(service_custom_url.url) == "https://custom.api.com"

    @pytest.mark.asyncio
    async def test_request_connection_error(self, service):
        """Test request with connection error."""
        mock_session = AsyncMock()
        mock_session.get.side_effect = aiohttp.ClientConnectionError(
            "Connection failed"
        )
        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch(
            "adapters.services.retroachievements.ctx_aiohttp_session", mock_context
        ):
            with pytest.raises(HTTPException) as exc_info:
                await service._request("https://retroachievements.org/API")

        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "Can't connect to RetroAchievements" in exc_info.value.detail


class TestRetroAchievementsServiceIntegration:
    @pytest.fixture
    def service(self):
        """Create a RetroAchievementsService instance for integration testing."""
        return RetroAchievementsService()

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_get_game_extended_details_real_api(
        self, service, mock_ctx_aiohttp_session
    ):
        """Test get_game_extended_details with real API call."""
        with patch(
            "adapters.services.retroachievements.ctx_aiohttp_session",
            mock_ctx_aiohttp_session,
        ):
            result = await service.get_game_extended_details(1)

        # Verify response structure
        assert isinstance(result, dict)
        assert "ID" in result or "GameID" in result
        assert "Title" in result
        assert "ConsoleID" in result

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_get_game_list_real_api(self, service, mock_ctx_aiohttp_session):
        """Test get_game_list with real API call."""
        with patch(
            "adapters.services.retroachievements.ctx_aiohttp_session",
            mock_ctx_aiohttp_session,
        ):
            result = await service.get_game_list(1, limit=5)

        # Verify response structure
        assert isinstance(result, list)
        if result:  # If there are games
            game = result[0]
            assert "ID" in game or "GameID" in game
            assert "Title" in game

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_get_game_list_with_options_real_api(
        self, service, mock_ctx_aiohttp_session
    ):
        """Test get_game_list with all options using real API call."""
        with patch(
            "adapters.services.retroachievements.ctx_aiohttp_session",
            mock_ctx_aiohttp_session,
        ):
            result = await service.get_game_list(
                1,
                only_games_with_achievements=True,
                include_hashes=True,
                limit=3,
                offset=0,
            )

        # Verify response structure
        assert isinstance(result, list)
        assert len(result) <= 3  # Should respect limit

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_get_user_completion_progress_real_api(
        self, service, mock_ctx_aiohttp_session
    ):
        """Test get_user_completion_progress with real API call."""
        with patch(
            "adapters.services.retroachievements.ctx_aiohttp_session",
            mock_ctx_aiohttp_session,
        ):
            result = await service.get_user_completion_progress("arcanecraeda", limit=5)

        assert isinstance(result, dict)
        if result:  # Non-empty response
            assert "Total" in result
            assert "Results" in result
            assert isinstance(result["Results"], list)

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_get_user_completion_progress_with_pagination_real_api(
        self, service, mock_ctx_aiohttp_session
    ):
        """Test get_user_completion_progress with pagination using real API call."""
        with patch(
            "adapters.services.retroachievements.ctx_aiohttp_session",
            mock_ctx_aiohttp_session,
        ):
            result = await service.get_user_completion_progress(
                "Scott", limit=3, offset=0
            )

        # Verify response structure
        assert isinstance(result, dict)
        assert "Total" in result
        assert "Results" in result
        assert len(result["Results"]) <= 3

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_iter_user_completion_progress_real_api(
        self, service, mock_ctx_aiohttp_session
    ):
        """Test iter_user_completion_progress with real API call."""
        with patch(
            "adapters.services.retroachievements.ctx_aiohttp_session",
            mock_ctx_aiohttp_session,
        ):
            results = []
            count = 0
            async for result in service.iter_user_completion_progress("Scott"):
                results.append(result)
                count += 1
                if count >= 5:  # Limit iterations for testing
                    break

        # Verify we got results
        assert len(results) > 0
        if results:
            result = results[0]
            assert isinstance(result, dict)
            # Check for expected fields in completion progress
            assert any(key in result for key in ["GameID", "ID", "Title"])

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_get_user_game_progress_real_api(
        self, service, mock_ctx_aiohttp_session
    ):
        """Test get_user_game_progress with real API call."""
        with patch(
            "adapters.services.retroachievements.ctx_aiohttp_session",
            mock_ctx_aiohttp_session,
        ):
            result = await service.get_user_game_progress("Scott", 1)

        # Verify response structure
        assert isinstance(result, dict)
        # The response should contain game info and user progress
        assert any(key in result for key in ["ID", "GameID", "Title"])

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_get_user_game_progress_with_award_metadata_real_api(
        self, service, mock_ctx_aiohttp_session
    ):
        """Test get_user_game_progress with award metadata using real API call."""
        with patch(
            "adapters.services.retroachievements.ctx_aiohttp_session",
            mock_ctx_aiohttp_session,
        ):
            result = await service.get_user_game_progress(
                "Scott", 1, include_award_metadata=True
            )

        # Verify response structure
        assert isinstance(result, dict)
        assert any(key in result for key in ["ID", "GameID", "Title"])

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_error_handling_real_api(self, service, mock_ctx_aiohttp_session):
        """Test error handling with real API calls."""
        with patch(
            "adapters.services.retroachievements.ctx_aiohttp_session",
            mock_ctx_aiohttp_session,
        ):
            with patch(
                "adapters.services.retroachievements.RETROACHIEVEMENTS_API_KEY",
                "invalid_key",
            ):
                # This should handle the error gracefully
                result = await service.get_game_extended_details(INVALID_GAME_ID)
                assert isinstance(result, list)
