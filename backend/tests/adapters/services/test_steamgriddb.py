import asyncio
import http
import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from fastapi import HTTPException, status

from adapters.services.steamgriddb import (
    SteamGridDBService,
    auth_middleware,
)
from adapters.services.steamgriddb_types import (
    SGDBDimension,
    SGDBMime,
    SGDBStyle,
    SGDBTag,
    SGDBType,
)

INVALID_GAME_ID = 999999


class TestAuthMiddleware:
    @patch("adapters.services.steamgriddb.STEAMGRIDDB_API_KEY", "test_api_key")
    @pytest.mark.asyncio
    async def test_auth_middleware_adds_bearer_token(self):
        """Test that auth middleware adds Bearer token to request headers."""
        # Create a real request-like object
        mock_request = MagicMock()
        mock_request.headers = {}

        mock_handler = AsyncMock()
        mock_response = MagicMock()
        mock_handler.return_value = mock_response

        result = await auth_middleware(mock_request, mock_handler)

        # Check that the Authorization header was added
        assert mock_request.headers["Authorization"] == "Bearer test_api_key"
        mock_handler.assert_called_once_with(mock_request)
        assert result == mock_response

    @patch("adapters.services.steamgriddb.STEAMGRIDDB_API_KEY", "")
    @pytest.mark.asyncio
    async def test_auth_middleware_with_empty_api_key(self):
        """Test that auth middleware adds empty Bearer token when none configured."""
        mock_request = MagicMock()
        mock_request.headers = {}

        mock_handler = AsyncMock()
        mock_response = MagicMock()
        mock_handler.return_value = mock_response

        result = await auth_middleware(mock_request, mock_handler)

        assert mock_request.headers["Authorization"] == "Bearer "
        assert result == mock_response


class TestSteamGridDBServiceUnit:
    """Unit tests with mocked dependencies."""

    @pytest.fixture
    def service(self):
        """Create a SteamGridDBService instance for testing."""
        return SteamGridDBService()

    @pytest.fixture
    def service_custom_url(self):
        """Create a SteamGridDBService instance with custom URL."""
        return SteamGridDBService("https://custom.api.com")

    def test_init_default_url(self, service):
        """Test service initialization with default URL."""
        assert str(service.url) == "https://steamgriddb.com/api/v2"

    def test_init_custom_url(self, service_custom_url):
        """Test service initialization with custom URL."""
        assert str(service_custom_url.url) == "https://custom.api.com"

    @pytest.mark.asyncio
    async def test_request_success(self, service):
        """Test successful API request."""
        mock_session = AsyncMock()
        mock_response = MagicMock()
        mock_response.json = AsyncMock(
            return_value={"data": [{"id": 1, "name": "Test Game"}]}
        )
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.steamgriddb.ctx_aiohttp_session", mock_context):
            result = await service._request(
                "https://steamgriddb.com/api/v2/search/test"
            )

        assert result == {"data": [{"id": 1, "name": "Test Game"}]}
        mock_session.get.assert_called_once()
        mock_response.raise_for_status.assert_called_once()
        mock_response.json.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_unauthorized_raises_exception(self, service):
        """Test that 401 Unauthorized raises SGDBInvalidAPIKeyException."""
        mock_session = AsyncMock()
        unauthorized_error = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=http.HTTPStatus.UNAUTHORIZED,
        )
        mock_session.get.side_effect = unauthorized_error

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.steamgriddb.ctx_aiohttp_session", mock_context):
            with pytest.raises(HTTPException) as exc_info:
                await service._request("https://steamgriddb.com/api/v2/search/test")
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

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

        with patch("adapters.services.steamgriddb.ctx_aiohttp_session", mock_context):
            result = await service._request(
                "https://steamgriddb.com/api/v2/search/test"
            )

        assert result == {}

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

        with patch("adapters.services.steamgriddb.ctx_aiohttp_session", mock_context):
            result = await service._request(
                "https://steamgriddb.com/api/v2/search/test"
            )

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_grids_for_game_basic(self, service):
        """Test get_grids_for_game with basic game ID."""
        mock_response = {
            "page": 0,
            "total": 2,
            "limit": 50,
            "data": [
                {
                    "id": 1,
                    "score": 100,
                    "style": "material",
                    "url": "https://example.com/grid1.png",
                    "thumb": "https://example.com/thumb1.png",
                    "tags": [],
                    "author": {"name": "TestUser", "steam64": "123", "avatar": ""},
                },
                {
                    "id": 2,
                    "score": 90,
                    "style": "alternate",
                    "url": "https://example.com/grid2.png",
                    "thumb": "https://example.com/thumb2.png",
                    "tags": ["humor"],
                    "author": {"name": "TestUser2", "steam64": "456", "avatar": ""},
                },
            ],
        }

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_grids_for_game(123)

        assert result["page"] == 0
        assert result["total"] == 2
        assert len(result["data"]) == 2
        assert result["data"][0]["id"] == 1
        call_args = mock_request.call_args[0][0]
        assert "grids/game/123" in call_args

    @pytest.mark.asyncio
    async def test_get_grids_for_game_with_styles(self, service):
        """Test get_grids_for_game with style filters."""
        mock_response = {
            "page": 0,
            "total": 1,
            "limit": 50,
            "data": [{"id": 1, "style": "material"}],
        }

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_grids_for_game(
                123, styles=[SGDBStyle.MATERIAL, SGDBStyle.ALTERNATE]
            )

        assert len(result["data"]) == 1
        call_args = mock_request.call_args[0][0]
        assert (
            "styles=material%2Calternate" in call_args
            or "styles=material,alternate" in call_args
        )

    @pytest.mark.asyncio
    async def test_get_grids_for_game_with_dimensions(self, service):
        """Test get_grids_for_game with dimension filters."""
        mock_response = {"page": 0, "total": 0, "limit": 50, "data": []}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_grids_for_game(
                123,
                dimensions=[
                    SGDBDimension.STEAM_HORIZONTAL,
                    SGDBDimension.STEAM_VERTICAL,
                ],
            )

        assert result["data"] == []
        call_args = mock_request.call_args[0][0]
        assert "dimensions=" in call_args

    @pytest.mark.asyncio
    async def test_get_grids_for_game_with_mimes(self, service):
        """Test get_grids_for_game with MIME type filters."""
        mock_response = {"page": 0, "total": 0, "limit": 50, "data": []}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_grids_for_game(
                123, mimes=[SGDBMime.PNG, SGDBMime.WEBP]
            )

        assert result["data"] == []
        call_args = mock_request.call_args[0][0]
        assert "mimes=" in call_args

    @pytest.mark.asyncio
    async def test_get_grids_for_game_with_types(self, service):
        """Test get_grids_for_game with type filters."""
        mock_response = {"page": 0, "total": 0, "limit": 50, "data": []}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_grids_for_game(
                123, types=[SGDBType.STATIC, SGDBType.ANIMATED]
            )

        assert result["data"] == []
        call_args = mock_request.call_args[0][0]
        assert "types=" in call_args

    @pytest.mark.asyncio
    async def test_get_grids_for_game_with_tags(self, service):
        """Test get_grids_for_game with tag filters."""
        mock_response = {"page": 0, "total": 0, "limit": 50, "data": []}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_grids_for_game(
                123, any_of_tags=[SGDBTag.HUMOR, SGDBTag.NSFW]
            )

        assert result["data"] == []
        call_args = mock_request.call_args[0][0]
        assert "oneoftag=" in call_args

    @pytest.mark.asyncio
    async def test_get_grids_for_game_with_boolean_filters(self, service):
        """Test get_grids_for_game with boolean filters."""
        mock_response = {"page": 0, "total": 0, "limit": 50, "data": []}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_grids_for_game(
                123, is_nsfw=True, is_humor=False, is_epilepsy="any"
            )

        assert result["data"] == []
        call_args = mock_request.call_args[0][0]
        assert "nsfw=true" in call_args
        assert "humor=false" in call_args
        assert "epilepsy=any" in call_args

    @pytest.mark.asyncio
    async def test_get_grids_for_game_with_pagination(self, service):
        """Test get_grids_for_game with pagination parameters."""
        mock_response = {"page": 1, "total": 100, "limit": 10, "data": []}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_grids_for_game(123, limit=10, page_number=1)

        assert result["page"] == 1
        assert result["limit"] == 10
        call_args = mock_request.call_args[0][0]
        assert "limit=10" in call_args
        assert "page=1" in call_args

    @pytest.mark.asyncio
    async def test_get_grids_for_game_with_all_parameters(self, service):
        """Test get_grids_for_game with all parameters."""
        mock_response = {"page": 0, "total": 0, "limit": 5, "data": []}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_grids_for_game(
                123,
                styles=[SGDBStyle.MATERIAL],
                dimensions=[SGDBDimension.STEAM_HORIZONTAL],
                mimes=[SGDBMime.PNG],
                types=[SGDBType.STATIC],
                any_of_tags=[SGDBTag.HUMOR],
                is_nsfw=False,
                is_humor=True,
                is_epilepsy="any",
                limit=5,
                page_number=0,
            )

        assert result["data"] == []
        call_args = mock_request.call_args[0][0]
        assert "styles=material" in call_args
        assert "dimensions=460x215" in call_args
        assert "mimes=image/png" in call_args
        assert "types=static" in call_args
        assert "oneoftag=humor" in call_args
        assert "nsfw=false" in call_args
        assert "humor=true" in call_args
        assert "epilepsy=any" in call_args
        assert "limit=5" in call_args
        assert "page=0" in call_args

    @pytest.mark.asyncio
    async def test_get_grids_for_game_empty_response(self, service):
        """Test get_grids_for_game with empty response."""
        mock_response: dict[str, list] = {}

        with patch.object(service, "_request", return_value=mock_response):
            result = await service.get_grids_for_game(123)

        assert result["page"] == 0
        assert result["total"] == 0
        assert result["limit"] == 50
        assert result["data"] == []

    @pytest.mark.asyncio
    async def test_iter_grids_for_game_single_page(self, service):
        """Test iter_grids_for_game with single page of results."""
        mock_grid_1 = {"id": 1, "score": 100}
        mock_grid_2 = {"id": 2, "score": 90}
        mock_response = {
            "page": 0,
            "total": 2,
            "limit": 50,
            "data": [mock_grid_1, mock_grid_2],
        }

        with patch.object(service, "get_grids_for_game", return_value=mock_response):
            results = []
            async for grid in service.iter_grids_for_game(123):
                results.append(grid)

        assert len(results) == 2
        assert results[0] == mock_grid_1
        assert results[1] == mock_grid_2

    @pytest.mark.asyncio
    async def test_iter_grids_for_game_multiple_pages(self, service):
        """Test iter_grids_for_game with multiple pages of results."""
        # First page
        mock_response_1 = {
            "page": 0,
            "total": 75,
            "limit": 50,
            "data": [{"id": i} for i in range(1, 51)],  # 50 items
        }
        # Second page
        mock_response_2 = {
            "page": 1,
            "total": 75,
            "limit": 50,
            "data": [{"id": i} for i in range(51, 76)],  # 25 items
        }

        with patch.object(
            service,
            "get_grids_for_game",
            side_effect=[mock_response_1, mock_response_2],
        ) as mock_get:
            results = []
            async for grid in service.iter_grids_for_game(123):
                results.append(grid)

        assert len(results) == 75
        assert results[0]["id"] == 1
        assert results[49]["id"] == 50
        assert results[50]["id"] == 51
        assert results[74]["id"] == 75
        assert mock_get.call_count == 2

    @pytest.mark.asyncio
    async def test_iter_grids_for_game_empty_results(self, service):
        """Test iter_grids_for_game with no results."""
        mock_response = {"page": 0, "total": 0, "limit": 50, "data": []}

        with patch.object(service, "get_grids_for_game", return_value=mock_response):
            results = []
            async for grid in service.iter_grids_for_game(123):
                results.append(grid)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_iter_grids_for_game_with_filters(self, service):
        """Test iter_grids_for_game with filters passed through."""
        mock_response = {"page": 0, "total": 1, "limit": 50, "data": [{"id": 1}]}

        with patch.object(
            service, "get_grids_for_game", return_value=mock_response
        ) as mock_get:
            results = []
            async for grid in service.iter_grids_for_game(
                123,
                styles=[SGDBStyle.MATERIAL],
                is_nsfw=False,
            ):
                results.append(grid)

        assert len(results) == 1
        # Verify filters were passed through
        mock_get.assert_called_with(
            123,
            styles=[SGDBStyle.MATERIAL],
            dimensions=None,
            mimes=None,
            types=None,
            any_of_tags=None,
            is_nsfw=False,
            is_humor=None,
            is_epilepsy=None,
            limit=50,
            page_number=0,
        )

    @pytest.mark.asyncio
    async def test_search_games_basic(self, service):
        """Test search_games with basic term."""
        mock_response = {
            "data": [
                {"id": 1, "name": "Test Game 1", "types": ["game"], "verified": True},
                {"id": 2, "name": "Test Game 2", "types": ["game"], "verified": False},
            ]
        }

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.search_games("test")

        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[0]["name"] == "Test Game 1"
        assert result[1]["id"] == 2
        call_args = mock_request.call_args[0][0]
        assert "search/autocomplete/test" in call_args

    @pytest.mark.asyncio
    async def test_search_games_no_results(self, service):
        """Test search_games with no results."""
        mock_response: dict[str, list] = {"data": []}

        with patch.object(service, "_request", return_value=mock_response):
            result = await service.search_games("nonexistent")

        assert result == []

    @pytest.mark.asyncio
    async def test_search_games_empty_response(self, service):
        """Test search_games with empty response."""
        mock_response: dict[str, list] = {}

        with patch.object(service, "_request", return_value=mock_response):
            result = await service.search_games("test")

        assert result == []

    @pytest.mark.asyncio
    async def test_search_games_special_characters(self, service):
        """Test search_games with special characters in term."""
        mock_response: dict[str, list] = {"data": []}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.search_games("Pac-Man & Ms. Pac-Man")

        assert result == []
        call_args = mock_request.call_args[0][0]
        assert "search/autocomplete/" in call_args


class TestSteamGridDBServiceIntegration:
    """Integration tests with real API calls using VCR cassettes."""

    @pytest.fixture
    def service(self):
        """Create a SteamGridDBService instance for integration testing."""
        return SteamGridDBService()

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_search_games_real_api(self, service, mock_ctx_aiohttp_session):
        """Test search_games with real API call."""
        with patch(
            "adapters.services.steamgriddb.ctx_aiohttp_session",
            mock_ctx_aiohttp_session,
        ):
            result = await service.search_games("Mario")

        # Verify response structure
        assert isinstance(result, list)
        if result:  # If there are games
            game = result[0]
            assert "id" in game
            assert "name" in game
            assert "types" in game
            assert "verified" in game

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_get_grids_for_game_real_api(self, service, mock_ctx_aiohttp_session):
        """Test get_grids_for_game with real API call."""
        with patch(
            "adapters.services.steamgriddb.ctx_aiohttp_session",
            mock_ctx_aiohttp_session,
        ):
            result = await service.get_grids_for_game(1, limit=5)

        # Verify response structure
        assert isinstance(result, dict)
        assert "page" in result
        assert "total" in result
        assert "limit" in result
        assert "data" in result
        assert isinstance(result["data"], list)
        if result["data"]:  # If there are grids
            grid = result["data"][0]
            assert "id" in grid
            assert "score" in grid
            assert "style" in grid
            assert "url" in grid

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_get_grids_for_game_with_filters_real_api(
        self, service, mock_ctx_aiohttp_session
    ):
        """Test get_grids_for_game with filters using real API call."""
        with patch(
            "adapters.services.steamgriddb.ctx_aiohttp_session",
            mock_ctx_aiohttp_session,
        ):
            result = await service.get_grids_for_game(
                1, styles=[SGDBStyle.MATERIAL], limit=3
            )

        # Verify response structure
        assert isinstance(result, dict)
        assert len(result["data"]) <= 3  # Should respect limit

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_iter_grids_for_game_real_api(
        self, service, mock_ctx_aiohttp_session
    ):
        """Test iter_grids_for_game with real API call."""
        with patch(
            "adapters.services.steamgriddb.ctx_aiohttp_session",
            mock_ctx_aiohttp_session,
        ):
            results = []
            count = 0
            async for grid in service.iter_grids_for_game(1):
                results.append(grid)
                count += 1
                if count >= 5:  # Limit iterations for testing
                    break

        # Verify we got results
        if results:
            grid = results[0]
            assert isinstance(grid, dict)
            assert "id" in grid
            assert "score" in grid
            assert "style" in grid

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_error_handling_real_api(self, service, mock_ctx_aiohttp_session):
        """Test error handling with real API calls."""
        with patch(
            "adapters.services.steamgriddb.ctx_aiohttp_session",
            mock_ctx_aiohttp_session,
        ):
            with patch(
                "adapters.services.steamgriddb.STEAMGRIDDB_API_KEY", "invalid_key"
            ):
                # This should handle the error gracefully
                try:
                    result = await service.get_grids_for_game(INVALID_GAME_ID)
                    # Should either return empty result or handle auth error
                    assert isinstance(result, dict)
                except HTTPException as exc:
                    # Should be authentication error with 401 status
                    assert exc.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_search_games_no_results_real_api(
        self, service, mock_ctx_aiohttp_session
    ):
        """Test search_games with term that returns no results using real API call."""
        with patch(
            "adapters.services.steamgriddb.ctx_aiohttp_session",
            mock_ctx_aiohttp_session,
        ):
            result = await service.search_games("ZZZNonexistentGameZZZ")

        # Should return empty list for no results
        assert result == []


# Performance tests
class TestSteamGridDBServicePerformance:
    """Performance tests for SteamGridDB service."""

    @pytest.fixture
    def service(self):
        """Create a SteamGridDBService instance for performance testing."""
        return SteamGridDBService()

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, service):
        """Test multiple concurrent API requests."""
        mock_response = {"data": [{"id": 1, "name": "Test Game"}]}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            # Run 5 concurrent requests
            tasks = [service.search_games("test") for _ in range(5)]
            results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(len(result) == 1 for result in results)
        assert len(results) == 5
        assert mock_request.call_count == 5

    @pytest.mark.asyncio
    async def test_concurrent_grid_requests(self, service):
        """Test multiple concurrent grid requests."""
        mock_response = {"page": 0, "total": 1, "limit": 50, "data": [{"id": 1}]}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            # Run 3 concurrent grid requests
            tasks = [service.get_grids_for_game(i) for i in range(1, 4)]
            results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(len(result["data"]) == 1 for result in results)
        assert len(results) == 3
        assert mock_request.call_count == 3

    @pytest.mark.asyncio
    async def test_iter_grids_pagination_performance(self, service):
        """Test performance of pagination in iter_grids_for_game."""
        # Mock multiple pages
        mock_responses = [
            {
                "page": 0,
                "total": 100,
                "limit": 50,
                "data": [{"id": i} for i in range(1, 51)],
            },
            {
                "page": 1,
                "total": 100,
                "limit": 50,
                "data": [{"id": i} for i in range(51, 101)],
            },
        ]

        with patch.object(
            service, "get_grids_for_game", side_effect=mock_responses
        ) as mock_get:
            results = []
            async for grid in service.iter_grids_for_game(123):
                results.append(grid)

        assert len(results) == 100
        assert mock_get.call_count == 2


# Edge case tests
class TestSteamGridDBServiceEdgeCases:
    """Edge case tests for SteamGridDB service."""

    @pytest.fixture
    def service(self):
        """Create a SteamGridDBService instance for edge case testing."""
        return SteamGridDBService()

    @pytest.mark.asyncio
    async def test_get_grids_for_game_with_empty_collections(self, service):
        """Test get_grids_for_game with empty collections."""
        mock_response = {"page": 0, "total": 0, "limit": 50, "data": []}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_grids_for_game(
                123,
                styles=[],
                dimensions=[],
                mimes=[],
                types=[],
                any_of_tags=[],
            )

        assert result["data"] == []
        call_args = mock_request.call_args[0][0]
        # Empty collections should not add parameters to URL
        assert "styles=" not in call_args
        assert "dimensions=" not in call_args
        assert "mimes=" not in call_args
        assert "types=" not in call_args
        assert "oneoftag=" not in call_args

    @pytest.mark.asyncio
    async def test_get_grids_for_game_with_zero_values(self, service):
        """Test get_grids_for_game with zero values."""
        mock_response = {"page": 0, "total": 0, "limit": 0, "data": []}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_grids_for_game(123, limit=0, page_number=0)

        assert result["data"] == []
        call_args = mock_request.call_args[0][0]
        assert "limit=0" in call_args
        assert "page=0" in call_args

    @pytest.mark.asyncio
    async def test_search_games_empty_term(self, service):
        """Test search_games with empty term."""
        mock_response: dict[str, list] = {"data": []}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.search_games("")

        assert result == []
        call_args = mock_request.call_args[0][0]
        assert "search/autocomplete/" in call_args

    @pytest.mark.asyncio
    async def test_request_with_custom_timeout(self, service):
        """Test request with custom timeout."""
        mock_session = AsyncMock()
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"data": []})
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.steamgriddb.ctx_aiohttp_session", mock_context):
            result = await service._request(
                "https://steamgriddb.com/api/v2/search/test", request_timeout=30
            )

        assert result == {"data": []}
        # Verify timeout was passed correctly
        call_kwargs = mock_session.get.call_args[1]
        assert call_kwargs["timeout"].total == 30

    @pytest.mark.asyncio
    async def test_iter_grids_stops_at_exact_total(self, service):
        """Test that iter_grids_for_game stops when reaching exact total."""
        # Mock response where we reach exact total
        mock_response = {
            "page": 0,
            "total": 50,
            "limit": 50,
            "data": [{"id": i} for i in range(1, 51)],  # Exactly 50 items
        }

        with patch.object(
            service, "get_grids_for_game", return_value=mock_response
        ) as mock_get:
            results = []
            async for grid in service.iter_grids_for_game(123):
                results.append(grid)

        assert len(results) == 50
        assert mock_get.call_count == 1  # Should only call once

    @pytest.mark.asyncio
    async def test_get_grids_boolean_filter_none_values(self, service):
        """Test get_grids_for_game with None values for boolean filters."""
        mock_response = {"page": 0, "total": 0, "limit": 50, "data": []}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_grids_for_game(
                123, is_nsfw=None, is_humor=None, is_epilepsy=None
            )

        assert result["data"] == []
        call_args = mock_request.call_args[0][0]
        # None values should not add parameters to URL
        assert "nsfw=" not in call_args
        assert "humor=" not in call_args
        assert "epilepsy=" not in call_args
