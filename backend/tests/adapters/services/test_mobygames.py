import asyncio
import http
import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
import yarl
from fastapi import HTTPException, status

from adapters.services.mobygames import (
    MobyGamesService,
    auth_middleware,
)

INVALID_GAME_ID = 999999

MockResponse = dict[str, list[dict[str, int]]]


class TestAuthMiddleware:
    @patch("adapters.services.mobygames.MOBYGAMES_API_KEY", "test_api_key")
    @pytest.mark.asyncio
    async def test_auth_middleware_adds_api_key(self):
        """Test that auth middleware adds API key to request URL."""
        # Create a real request-like object
        mock_request = MagicMock()
        mock_request.url = yarl.URL("https://api.mobygames.com/v1/games")

        mock_handler = AsyncMock()
        mock_response = MagicMock()
        mock_handler.return_value = mock_response

        result = await auth_middleware(mock_request, mock_handler)

        # Check that the URL now contains the API key
        expected_url = yarl.URL("https://api.mobygames.com/v1/games").with_query(
            api_key="test_api_key"
        )
        assert mock_request.url == expected_url
        mock_handler.assert_called_once_with(mock_request)
        assert result == mock_response

    @patch("adapters.services.mobygames.MOBYGAMES_API_KEY", "")
    @pytest.mark.asyncio
    async def test_auth_middleware_with_empty_api_key(self):
        """Test that auth middleware adds empty API key when none configured."""
        mock_request = MagicMock()
        mock_request.url = yarl.URL("https://api.mobygames.com/v1/games")

        mock_handler = AsyncMock()
        mock_response = MagicMock()
        mock_handler.return_value = mock_response

        result = await auth_middleware(mock_request, mock_handler)

        expected_url = yarl.URL("https://api.mobygames.com/v1/games").with_query(
            api_key=""
        )
        assert mock_request.url == expected_url
        assert result == mock_response


class TestMobyGamesServiceUnit:
    """Unit tests with mocked dependencies."""

    @pytest.fixture
    def service(self):
        """Create a MobyGamesService instance for testing."""
        return MobyGamesService()

    @pytest.fixture
    def service_custom_url(self):
        """Create a MobyGamesService instance with custom URL."""
        return MobyGamesService("https://custom.api.com")

    def test_init_default_url(self, service):
        """Test service initialization with default URL."""
        assert str(service.url) == "https://api.mobygames.com/v1"

    def test_init_custom_url(self, service_custom_url):
        """Test service initialization with custom URL."""
        assert str(service_custom_url.url) == "https://custom.api.com"

    @pytest.mark.asyncio
    async def test_request_success(self, service):
        """Test successful API request."""
        mock_session = AsyncMock()
        mock_response = MagicMock()
        mock_response.json = AsyncMock(
            return_value={"games": [{"game_id": 1, "title": "Test Game"}]},
        )
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.mobygames.ctx_aiohttp_session", mock_context):
            result = await service._request("https://api.mobygames.com/v1/games")

        assert result == {"games": [{"game_id": 1, "title": "Test Game"}]}
        mock_session.get.assert_called_once()
        mock_response.raise_for_status.assert_called_once()
        mock_response.json.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_connection_error(self, service):
        """Test request with connection error."""
        mock_session = AsyncMock()
        mock_session.get.side_effect = aiohttp.ClientConnectionError(
            "Connection failed"
        )
        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.mobygames.ctx_aiohttp_session", mock_context):
            with pytest.raises(HTTPException) as exc_info:
                await service._request("https://api.mobygames.com/v1/games")

        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "Can't connect to MobyGames" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_request_timeout_with_retry(self, service):
        """Test request timeout with successful retry."""
        mock_session = AsyncMock()
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"games": []})
        mock_response.raise_for_status.return_value = None

        # First call times out, second succeeds
        mock_session.get.side_effect = [
            aiohttp.ServerTimeoutError("Timeout"),
            mock_response,
        ]

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.mobygames.ctx_aiohttp_session", mock_context):
            result = await service._request("https://api.mobygames.com/v1/games")

        assert result == {"games": []}
        assert mock_session.get.call_count == 2

    @pytest.mark.asyncio
    async def test_request_unauthorized_returns_empty_dict(self, service):
        """Test that 401 Unauthorized returns empty dict."""
        mock_session = AsyncMock()
        unauthorized_error = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=http.HTTPStatus.UNAUTHORIZED,
        )
        mock_session.get.side_effect = unauthorized_error

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.mobygames.ctx_aiohttp_session", mock_context):
            result = await service._request("https://api.mobygames.com/v1/games")

        assert result == {}

    @pytest.mark.asyncio
    async def test_request_rate_limit_with_retry(self, service):
        """Test rate limit handling with retry."""
        mock_session = AsyncMock()
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"games": []})
        mock_response.raise_for_status.return_value = None

        # First call hits rate limit, second succeeds
        rate_limit_error = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=http.HTTPStatus.TOO_MANY_REQUESTS,
        )
        mock_session.get.side_effect = [rate_limit_error, mock_response]

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.mobygames.ctx_aiohttp_session", mock_context):
            with patch("asyncio.sleep") as mock_sleep:
                result = await service._request("https://api.mobygames.com/v1/games")

        assert result == {
            "games": []
        }  # First call returns empty dict, retry happens on second call
        mock_sleep.assert_called_once_with(2)

    @pytest.mark.asyncio
    async def test_request_json_decode_error(self, service):
        """Test handling of JSON decode error."""
        mock_session = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
        mock_session.get.return_value = mock_response

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.mobygames.ctx_aiohttp_session", mock_context):
            result = await service._request("https://api.mobygames.com/v1/games")

        assert result == {}

    @pytest.mark.asyncio
    async def test_request_other_client_error(self, service):
        """Test handling of other client errors."""
        mock_session = AsyncMock()
        client_error = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=http.HTTPStatus.BAD_REQUEST,
        )
        mock_session.get.side_effect = client_error

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.mobygames.ctx_aiohttp_session", mock_context):
            result = await service._request("https://api.mobygames.com/v1/games")

        assert result == {}

    @pytest.mark.asyncio
    async def test_list_games_default_parameters(self, service):
        """Test list_games with default parameters."""
        mock_response = {"games": [{"game_id": 1, "title": "Test Game"}]}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.list_games()

        assert result == [{"game_id": 1, "title": "Test Game"}]
        mock_request.assert_called_once()
        call_args = mock_request.call_args[0][0]
        assert "https://api.mobygames.com/v1/games" in call_args

    @pytest.mark.asyncio
    async def test_list_games_with_game_id(self, service):
        """Test list_games with specific game ID."""
        mock_response = {"games": [{"game_id": 123, "title": "Specific Game"}]}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.list_games(game_id=123)

        assert result == [{"game_id": 123, "title": "Specific Game"}]
        call_args = mock_request.call_args[0][0]
        assert "id=123" in call_args

    @pytest.mark.asyncio
    async def test_list_games_with_platform_ids(self, service):
        """Test list_games with platform IDs."""
        mock_response: MockResponse = {"games": []}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.list_games(platform_ids=[1, 2, 3])

        assert result == []
        call_args = mock_request.call_args[0][0]
        assert "platform=1" in call_args
        assert "platform=2" in call_args
        assert "platform=3" in call_args

    @pytest.mark.asyncio
    async def test_list_games_with_genre_ids(self, service):
        """Test list_games with genre IDs."""
        mock_response: MockResponse = {"games": []}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.list_games(genre_ids=[5, 10])

        assert result == []
        call_args = mock_request.call_args[0][0]
        assert "genre=5" in call_args
        assert "genre=10" in call_args

    @pytest.mark.asyncio
    async def test_list_games_with_group_ids(self, service):
        """Test list_games with group IDs."""
        mock_response: MockResponse = {"games": []}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.list_games(group_ids=[100, 200])

        assert result == []
        call_args = mock_request.call_args[0][0]
        assert "group=100" in call_args
        assert "group=200" in call_args

    @pytest.mark.asyncio
    async def test_list_games_with_title(self, service):
        """Test list_games with title search."""
        mock_response: MockResponse = {"games": []}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.list_games(title="Sonic")

        assert result == []
        call_args = mock_request.call_args[0][0]
        assert "title=Sonic" in call_args

    @pytest.mark.asyncio
    async def test_list_games_with_output_format_id(self, service):
        """Test list_games with ID output format."""
        mock_response = {"games": [1, 2, 3]}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.list_games(output_format="id")

        assert result == [1, 2, 3]
        call_args = mock_request.call_args[0][0]
        assert "format=id" in call_args

    @pytest.mark.asyncio
    async def test_list_games_with_output_format_brief(self, service):
        """Test list_games with brief output format."""
        mock_response = {"games": [{"game_id": 1, "title": "Test", "moby_url": "url"}]}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.list_games(output_format="brief")

        assert result == [{"game_id": 1, "title": "Test", "moby_url": "url"}]
        call_args = mock_request.call_args[0][0]
        assert "format=brief" in call_args

    @pytest.mark.asyncio
    async def test_list_games_with_pagination(self, service):
        """Test list_games with limit and offset."""
        mock_response: MockResponse = {"games": []}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.list_games(limit=10, offset=20)

        assert result == []
        call_args = mock_request.call_args[0][0]
        assert "limit=10" in call_args
        assert "offset=20" in call_args

    @pytest.mark.asyncio
    async def test_list_games_with_all_parameters(self, service):
        """Test list_games with all parameters."""
        mock_response: MockResponse = {"games": []}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.list_games(
                game_id=1,
                platform_ids=[2, 3],
                genre_ids=[4, 5],
                group_ids=[6, 7],
                title="Test Game",
                output_format="normal",
                limit=5,
                offset=10,
            )

        assert result == []
        call_args = mock_request.call_args[0][0]
        assert "id=1" in call_args
        assert "platform=2" in call_args
        assert "platform=3" in call_args
        assert "genre=4" in call_args
        assert "genre=5" in call_args
        assert "group=6" in call_args
        assert "group=7" in call_args
        assert "title=Test+Game" in call_args or "title=Test%20Game" in call_args
        assert "format=normal" in call_args
        assert "limit=5" in call_args
        assert "offset=10" in call_args

    @pytest.mark.asyncio
    async def test_list_games_empty_response(self, service):
        """Test list_games with empty response."""
        mock_response: MockResponse = {}

        with patch.object(service, "_request", return_value=mock_response):
            result = await service.list_games()

        assert result == []

    @pytest.mark.asyncio
    async def test_list_games_missing_games_key(self, service):
        """Test list_games with missing games key in response."""
        mock_response = {"total": 0}

        with patch.object(service, "_request", return_value=mock_response):
            result = await service.list_games()

        assert result == []


class TestMobyGamesServiceIntegration:
    """Integration tests with real API calls using VCR cassettes."""

    @pytest.fixture
    def service(self):
        """Create a MobyGamesService instance for integration testing."""
        return MobyGamesService()

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_list_games_real_api(self, service, mock_ctx_aiohttp_session):
        """Test list_games with real API call."""
        with patch(
            "adapters.services.mobygames.ctx_aiohttp_session", mock_ctx_aiohttp_session
        ):
            result = await service.list_games(limit=5)

        # Verify response structure
        assert isinstance(result, list)
        if result:  # If there are games
            game = result[0]
            assert "game_id" in game
            assert "title" in game

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_list_games_with_platform_filter_real_api(
        self, service, mock_ctx_aiohttp_session
    ):
        """Test list_games with platform filter using real API call."""
        with patch(
            "adapters.services.mobygames.ctx_aiohttp_session", mock_ctx_aiohttp_session
        ):
            result = await service.list_games(platform_ids=[1], limit=3)  # PC platform

        # Verify response structure
        assert isinstance(result, list)
        assert len(result) <= 3  # Should respect limit
        if result:
            game = result[0]
            assert "game_id" in game
            assert "title" in game

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_list_games_with_title_search_real_api(
        self, service, mock_ctx_aiohttp_session
    ):
        """Test list_games with title search using real API call."""
        with patch(
            "adapters.services.mobygames.ctx_aiohttp_session", mock_ctx_aiohttp_session
        ):
            result = await service.list_games(title="Sonic", limit=5)

        # Verify response structure
        assert isinstance(result, list)
        if result:
            game = result[0]
            assert "game_id" in game
            assert "title" in game
            # Title should contain "Sonic" (case insensitive)
            assert "sonic" in game["title"].lower()

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_list_games_brief_format_real_api(
        self, service, mock_ctx_aiohttp_session
    ):
        """Test list_games with brief output format using real API call."""
        with patch(
            "adapters.services.mobygames.ctx_aiohttp_session", mock_ctx_aiohttp_session
        ):
            result = await service.list_games(output_format="brief", limit=3)

        # Verify response structure for brief format
        assert isinstance(result, list)
        if result:
            game = result[0]
            assert "game_id" in game
            assert "title" in game
            assert "moby_url" in game
            # Brief format should not have detailed fields
            assert "description" not in game
            assert "genres" not in game

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_list_games_id_format_real_api(
        self, service, mock_ctx_aiohttp_session
    ):
        """Test list_games with ID output format using real API call."""
        with patch(
            "adapters.services.mobygames.ctx_aiohttp_session", mock_ctx_aiohttp_session
        ):
            result = await service.list_games(output_format="id", limit=5)

        # Verify response structure for ID format
        assert isinstance(result, list)
        if result:
            # Should return list of integers (game IDs)
            assert all(isinstance(game_id, int) for game_id in result)

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_list_games_normal_format_real_api(
        self, service, mock_ctx_aiohttp_session
    ):
        """Test list_games with normal output format using real API call."""
        with patch(
            "adapters.services.mobygames.ctx_aiohttp_session", mock_ctx_aiohttp_session
        ):
            result = await service.list_games(output_format="normal", limit=2)

        # Verify response structure for normal format
        assert isinstance(result, list)
        if result:
            game = result[0]
            assert "game_id" in game
            assert "title" in game
            # Normal format should have detailed fields
            expected_fields = [
                "description",
                "genres",
                "platforms",
                "moby_url",
                "alternate_titles",
            ]
            # Check that at least some detailed fields are present
            assert any(field in game for field in expected_fields)

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_error_handling_real_api(self, service, mock_ctx_aiohttp_session):
        """Test error handling with real API calls."""
        with patch(
            "adapters.services.mobygames.ctx_aiohttp_session", mock_ctx_aiohttp_session
        ):
            with patch("adapters.services.mobygames.MOBYGAMES_API_KEY", "invalid_key"):
                # This should handle the error gracefully
                result = await service.list_games(game_id=INVALID_GAME_ID)
                assert isinstance(result, list)

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_list_games_with_pagination_real_api(
        self, service, mock_ctx_aiohttp_session
    ):
        """Test list_games with pagination using real API call."""
        with patch(
            "adapters.services.mobygames.ctx_aiohttp_session", mock_ctx_aiohttp_session
        ):
            result = await service.list_games(limit=2, offset=0)

        # Verify response structure
        assert isinstance(result, list)
        assert len(result) <= 2  # Should respect limit

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_list_games_with_genre_filter_real_api(
        self, service, mock_ctx_aiohttp_session
    ):
        """Test list_games with genre filter using real API call."""
        with patch(
            "adapters.services.mobygames.ctx_aiohttp_session", mock_ctx_aiohttp_session
        ):
            result = await service.list_games(genre_ids=[1], limit=3)  # Action genre

        # Verify response structure
        assert isinstance(result, list)
        if result:
            game = result[0]
            assert "game_id" in game
            assert "title" in game


# Performance tests
class TestMobyGamesServicePerformance:
    """Performance tests for MobyGames service."""

    @pytest.fixture
    def service(self):
        """Create a MobyGamesService instance for performance testing."""
        return MobyGamesService()

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, service):
        """Test multiple concurrent API requests."""
        mock_response = {"games": [{"game_id": 1, "title": "Test Game"}]}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            # Run 5 concurrent requests
            tasks = [service.list_games(limit=1) for _ in range(5)]
            results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(len(result) == 1 for result in results)
        assert len(results) == 5
        assert mock_request.call_count == 5

    @pytest.mark.asyncio
    async def test_request_timeout_handling(self, service):
        """Test handling of request timeouts."""
        mock_session = AsyncMock()

        # Simulate timeout on first call, success on retry
        timeout_error = aiohttp.ServerTimeoutError("Request timeout")
        success_response = MagicMock()
        success_response.json = AsyncMock(return_value={"games": []})
        success_response.raise_for_status.return_value = None

        mock_session.get.side_effect = [timeout_error, success_response]

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.mobygames.ctx_aiohttp_session", mock_context):
            result = await service._request(
                "https://api.mobygames.com/v1/games", request_timeout=1
            )

        assert result == {"games": []}
        assert mock_session.get.call_count == 2


# Edge case tests
class TestMobyGamesServiceEdgeCases:
    """Edge case tests for MobyGames service."""

    @pytest.fixture
    def service(self):
        """Create a MobyGamesService instance for edge case testing."""
        return MobyGamesService()

    @pytest.mark.asyncio
    async def test_list_games_with_empty_collections(self, service):
        """Test list_games with empty collections."""
        mock_response: MockResponse = {"games": []}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.list_games(
                platform_ids=[],
                genre_ids=[],
                group_ids=[],
            )

        assert result == []
        # Empty collections should not add parameters to URL
        call_args = mock_request.call_args[0][0]
        assert "platform=" not in call_args
        assert "genre=" not in call_args
        assert "group=" not in call_args

    @pytest.mark.asyncio
    async def test_list_games_with_zero_limit(self, service):
        """Test list_games with zero limit."""
        mock_response: MockResponse = {"games": []}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.list_games(limit=0)

        assert result == []
        call_args = mock_request.call_args[0][0]
        assert "limit=0" in call_args

    @pytest.mark.asyncio
    async def test_list_games_with_zero_offset(self, service):
        """Test list_games with zero offset."""
        mock_response: MockResponse = {"games": []}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.list_games(offset=0)

        assert result == []
        call_args = mock_request.call_args[0][0]
        assert "offset=0" in call_args

    @pytest.mark.asyncio
    async def test_list_games_with_special_characters_in_title(self, service):
        """Test list_games with special characters in title."""
        mock_response: MockResponse = {"games": []}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.list_games(title="Pac-Man & Ms. Pac-Man")

        assert result == []
        call_args = mock_request.call_args[0][0]
        # URL should be properly encoded
        assert "title=" in call_args

    @pytest.mark.asyncio
    async def test_request_with_custom_timeout(self, service):
        """Test request with custom timeout."""
        mock_session = AsyncMock()
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"games": []})
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.mobygames.ctx_aiohttp_session", mock_context):
            result = await service._request(
                "https://api.mobygames.com/v1/games", request_timeout=30
            )

        assert result == {"games": []}
        # Verify timeout was passed correctly
        call_kwargs = mock_session.get.call_args[1]
        assert call_kwargs["timeout"].total == 30
