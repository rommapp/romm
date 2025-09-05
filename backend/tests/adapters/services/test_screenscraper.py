import asyncio
import base64
import http
import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
import yarl
from fastapi import HTTPException, status

from adapters.services.screenscraper import (
    LOGIN_ERROR_CHECK,
    SS_DEV_ID,
    SS_DEV_PASSWORD,
    ScreenScraperService,
    auth_middleware,
)

INVALID_GAME_ID = 999999
INVALID_SYSTEM_ID = 999999


class TestScreenScraperConstants:
    """Test ScreenScraper constants and configuration."""

    def test_ss_dev_id_decoded(self):
        """Test that SS_DEV_ID is properly decoded."""
        expected = base64.b64decode("enVyZGkxNQ==").decode()
        assert SS_DEV_ID == expected

    def test_ss_dev_password_decoded(self):
        """Test that SS_DEV_PASSWORD is properly decoded."""
        expected = base64.b64decode("eFRKd29PRmpPUUc=").decode()
        assert SS_DEV_PASSWORD == expected

    def test_login_error_check_constant(self):
        """Test that LOGIN_ERROR_CHECK constant is defined."""
        assert LOGIN_ERROR_CHECK == "Erreur de login"


class TestAuthMiddleware:
    @patch("adapters.services.screenscraper.SCREENSCRAPER_USER", "test_user")
    @patch("adapters.services.screenscraper.SCREENSCRAPER_PASSWORD", "test_pass")
    @pytest.mark.asyncio
    async def test_auth_middleware_adds_auth_params(self):
        """Test that auth middleware adds all required authentication parameters."""
        # Create a real request-like object
        mock_request = MagicMock()
        mock_request.url = yarl.URL("https://api.screenscraper.fr/api2/jeuInfos.php")

        mock_handler = AsyncMock()
        mock_response = MagicMock()
        mock_handler.return_value = mock_response

        result = await auth_middleware(mock_request, mock_handler)

        # Check that the URL now contains all auth parameters
        expected_params = {
            "devid": SS_DEV_ID,
            "devpassword": SS_DEV_PASSWORD,
            "output": "json",
            "softname": "romm",
            "ssid": "test_user",
            "sspassword": "test_pass",
        }
        expected_url = yarl.URL(
            "https://api.screenscraper.fr/api2/jeuInfos.php"
        ).with_query(**expected_params)
        assert mock_request.url == expected_url
        mock_handler.assert_called_once_with(mock_request)
        assert result == mock_response

    @patch("adapters.services.screenscraper.SCREENSCRAPER_USER", "")
    @patch("adapters.services.screenscraper.SCREENSCRAPER_PASSWORD", "")
    @pytest.mark.asyncio
    async def test_auth_middleware_with_empty_credentials(self):
        """Test that auth middleware adds empty credentials when none configured."""
        mock_request = MagicMock()
        mock_request.url = yarl.URL("https://api.screenscraper.fr/api2/jeuInfos.php")

        mock_handler = AsyncMock()
        mock_response = MagicMock()
        mock_handler.return_value = mock_response

        result = await auth_middleware(mock_request, mock_handler)

        expected_params = {
            "devid": SS_DEV_ID,
            "devpassword": SS_DEV_PASSWORD,
            "output": "json",
            "softname": "romm",
            "ssid": "",
            "sspassword": "",
        }
        expected_url = yarl.URL(
            "https://api.screenscraper.fr/api2/jeuInfos.php"
        ).with_query(**expected_params)
        assert mock_request.url == expected_url
        assert result == mock_response


class TestScreenScraperServiceUnit:
    """Unit tests with mocked dependencies."""

    @pytest.fixture
    def service(self):
        """Create a ScreenScraperService instance for testing."""
        return ScreenScraperService()

    @pytest.fixture
    def service_custom_url(self):
        """Create a ScreenScraperService instance with custom URL."""
        return ScreenScraperService("https://custom.api.com")

    def test_init_default_url(self, service):
        """Test service initialization with default URL."""
        assert str(service.url) == "https://api.screenscraper.fr/api2"

    def test_init_custom_url(self, service_custom_url):
        """Test service initialization with custom URL."""
        assert str(service_custom_url.url) == "https://custom.api.com"

    @pytest.mark.asyncio
    async def test_request_success(self, service):
        """Test successful API request."""
        mock_session = AsyncMock()
        mock_response = MagicMock()
        mock_response.json = AsyncMock(
            return_value={"response": {"jeu": {"id": "1", "noms": []}}}
        )
        mock_response.text = AsyncMock(
            return_value='{"response": {"jeu": {"id": "1"}}}'
        )
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            result = await service._request(
                "https://api.screenscraper.fr/api2/jeuInfos.php"
            )

        assert result == {"response": {"jeu": {"id": "1", "noms": []}}}
        mock_session.get.assert_called_once()
        mock_response.raise_for_status.assert_called_once()
        mock_response.json.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_login_error(self, service):
        """Test request with login error in response text."""
        mock_session = AsyncMock()
        mock_response = MagicMock()
        mock_response.text = AsyncMock(
            return_value="Erreur de login: invalid credentials"
        )
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            with pytest.raises(HTTPException) as exc_info:
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid ScreenScraper credentials" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_request_connection_error(self, service):
        """Test request with connection error."""
        mock_session = AsyncMock()
        mock_session.get.side_effect = aiohttp.ClientConnectionError(
            "Connection failed"
        )
        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            with pytest.raises(HTTPException) as exc_info:
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "Can't connect to ScreenScraper" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_request_timeout_with_retry(self, service):
        """Test request timeout with successful retry."""
        mock_session = AsyncMock()
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"response": {"jeu": {}}})
        mock_response.text = AsyncMock(return_value='{"response": {"jeu": {}}}')
        mock_response.raise_for_status.return_value = None

        # First call times out, second succeeds
        mock_session.get.side_effect = [
            aiohttp.ServerTimeoutError("Timeout"),
            mock_response,
        ]

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            result = await service._request(
                "https://api.screenscraper.fr/api2/jeuInfos.php"
            )

        assert result == {"response": {"jeu": {}}}
        assert mock_session.get.call_count == 2

    @pytest.mark.asyncio
    async def test_request_rate_limit_with_retry(self, service):
        """Test rate limit handling with retry."""
        mock_session = AsyncMock()
        rate_limit_error = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=http.HTTPStatus.TOO_MANY_REQUESTS,
        )
        mock_session.get.side_effect = rate_limit_error

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            with patch("asyncio.sleep") as mock_sleep:
                result = await service._request(
                    "https://api.screenscraper.fr/api2/jeuInfos.php"
                )

        assert result == {}
        mock_sleep.assert_called_once_with(2)

    @pytest.mark.asyncio
    async def test_request_unauthorized_returns_empty_dict(self, service):
        """Test that unauthorized error in retry returns empty dict."""
        mock_session = AsyncMock()

        # First call timeout, second call unauthorized
        timeout_error = aiohttp.ServerTimeoutError("Timeout")
        unauthorized_error = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=http.HTTPStatus.UNAUTHORIZED,
        )
        mock_session.get.side_effect = [timeout_error, unauthorized_error]

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            result = await service._request(
                "https://api.screenscraper.fr/api2/jeuInfos.php"
            )

        assert result == {}

    @pytest.mark.asyncio
    async def test_request_json_decode_error(self, service):
        """Test handling of JSON decode error."""
        mock_session = AsyncMock()
        mock_response = MagicMock()
        mock_response.text = AsyncMock(return_value="Valid response text")
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
        mock_session.get.return_value = mock_response

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            result = await service._request(
                "https://api.screenscraper.fr/api2/jeuInfos.php"
            )

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

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            result = await service._request(
                "https://api.screenscraper.fr/api2/jeuInfos.php"
            )

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_game_info_with_crc(self, service):
        """Test get_game_info with CRC parameter."""
        mock_response = {
            "response": {
                "jeu": {
                    "id": "1",
                    "noms": [{"region": "wor", "text": "Test Game"}],
                    "systeme": {"id": "1", "text": "NES"},
                }
            }
        }

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_game_info(crc="ABC123")

        assert result is not None
        assert result["id"] == "1"
        call_args = mock_request.call_args[0][0]
        assert "crc=ABC123" in call_args

    @pytest.mark.asyncio
    async def test_get_game_info_with_md5(self, service):
        """Test get_game_info with MD5 parameter."""
        mock_response = {"response": {"jeu": {"id": "1"}}}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_game_info(md5="abc123def456")

        assert result is not None
        call_args = mock_request.call_args[0][0]
        assert "md5=abc123def456" in call_args

    @pytest.mark.asyncio
    async def test_get_game_info_with_sha1(self, service):
        """Test get_game_info with SHA1 parameter."""
        mock_response = {"response": {"jeu": {"id": "1"}}}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_game_info(sha1="abc123def456789")

        assert result is not None
        call_args = mock_request.call_args[0][0]
        assert "sha1=abc123def456789" in call_args

    @pytest.mark.asyncio
    async def test_get_game_info_with_system_id(self, service):
        """Test get_game_info with system ID parameter."""
        mock_response = {"response": {"jeu": {"id": "1"}}}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_game_info(system_id=1)

        assert result is not None
        call_args = mock_request.call_args[0][0]
        assert "systemeid=1" in call_args

    @pytest.mark.asyncio
    async def test_get_game_info_with_rom_type(self, service):
        """Test get_game_info with ROM type parameter."""
        mock_response = {"response": {"jeu": {"id": "1"}}}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_game_info(rom_type="rom")

        assert result is not None
        call_args = mock_request.call_args[0][0]
        assert "romtype=rom" in call_args

    @pytest.mark.asyncio
    async def test_get_game_info_with_rom_name(self, service):
        """Test get_game_info with ROM name parameter."""
        mock_response = {"response": {"jeu": {"id": "1"}}}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_game_info(rom_name="Test Game.nes")

        assert result is not None
        call_args = mock_request.call_args[0][0]
        assert (
            "romnom=Test+Game.nes" in call_args or "romnom=Test%20Game.nes" in call_args
        )

    @pytest.mark.asyncio
    async def test_get_game_info_with_rom_size(self, service):
        """Test get_game_info with ROM size parameter."""
        mock_response = {"response": {"jeu": {"id": "1"}}}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_game_info(rom_size_bytes=32768)

        assert result is not None
        call_args = mock_request.call_args[0][0]
        assert "romtaille=32768" in call_args

    @pytest.mark.asyncio
    async def test_get_game_info_with_serial_number(self, service):
        """Test get_game_info with serial number parameter."""
        mock_response = {"response": {"jeu": {"id": "1"}}}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_game_info(serial_number="NES-ABC-USA")

        assert result is not None
        call_args = mock_request.call_args[0][0]
        assert "serialnum=NES-ABC-USA" in call_args

    @pytest.mark.asyncio
    async def test_get_game_info_with_game_id(self, service):
        """Test get_game_info with game ID parameter."""
        mock_response = {"response": {"jeu": {"id": "123"}}}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_game_info(game_id=123)

        assert result is not None
        assert result["id"] == "123"
        call_args = mock_request.call_args[0][0]
        assert "gameid=123" in call_args

    @pytest.mark.asyncio
    async def test_get_game_info_with_all_parameters(self, service):
        """Test get_game_info with all parameters."""
        mock_response = {"response": {"jeu": {"id": "1"}}}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_game_info(
                crc="ABC123",
                md5="md5hash",
                sha1="sha1hash",
                system_id=1,
                rom_type="rom",
                rom_name="Test Game",
                rom_size_bytes=32768,
                serial_number="NES-ABC-USA",
                game_id=123,
            )

        assert result is not None
        call_args = mock_request.call_args[0][0]
        assert "crc=ABC123" in call_args
        assert "md5=md5hash" in call_args
        assert "sha1=sha1hash" in call_args
        assert "systemeid=1" in call_args
        assert "romtype=rom" in call_args
        assert "romtaille=32768" in call_args
        assert "serialnum=NES-ABC-USA" in call_args
        assert "gameid=123" in call_args

    @pytest.mark.asyncio
    async def test_get_game_info_no_game_found(self, service):
        """Test get_game_info when no game is found."""
        mock_response: dict[str, dict] = {"response": {}}

        with patch.object(service, "_request", return_value=mock_response):
            result = await service.get_game_info(crc="NOTFOUND")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_game_info_empty_jeu_data(self, service):
        """Test get_game_info when jeu data is empty."""
        mock_response: dict[str, dict] = {"response": {"jeu": {}}}

        with patch.object(service, "_request", return_value=mock_response):
            result = await service.get_game_info(crc="EMPTY")

        assert result is None

    @pytest.mark.asyncio
    async def test_search_games_basic(self, service):
        """Test search_games with basic term."""
        mock_response = {
            "response": {
                "jeux": [
                    {"id": "1", "noms": [{"region": "wor", "text": "Sonic"}]},
                    {"id": "2", "noms": [{"region": "wor", "text": "Sonic 2"}]},
                ]
            }
        }

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.search_games(term="Sonic")

        assert len(result) == 2
        assert result[0]["id"] == "1"
        assert result[1]["id"] == "2"
        call_args = mock_request.call_args[0][0]
        assert "recherche=Sonic" in call_args

    @pytest.mark.asyncio
    async def test_search_games_with_system_id(self, service):
        """Test search_games with system ID filter."""
        mock_response = {"response": {"jeux": [{"id": "1"}]}}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.search_games(term="Mario", system_id=7)

        assert len(result) == 1
        call_args = mock_request.call_args[0][0]
        assert "recherche=Mario" in call_args
        assert "systemeid=7" in call_args

    @pytest.mark.asyncio
    async def test_search_games_no_results(self, service):
        """Test search_games when no games are found."""
        mock_response: dict[str, dict] = {"response": {"jeux": []}}

        with patch.object(service, "_request", return_value=mock_response):
            result = await service.search_games(term="NonexistentGame")

        assert result == []

    @pytest.mark.asyncio
    async def test_search_games_empty_response(self, service):
        """Test search_games with empty response."""
        mock_response: dict[str, dict] = {"response": {}}

        with patch.object(service, "_request", return_value=mock_response):
            result = await service.search_games(term="Test")

        assert result == []

    @pytest.mark.asyncio
    async def test_search_games_special_characters(self, service):
        """Test search_games with special characters in term."""
        mock_response: dict[str, dict] = {"response": {"jeux": []}}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.search_games(term="Pac-Man & Ms. Pac-Man")

        assert result == []
        call_args = mock_request.call_args[0][0]
        assert "recherche=" in call_args


class TestScreenScraperServiceIntegration:
    """Integration tests with real API calls using VCR cassettes."""

    @pytest.fixture
    def service(self):
        """Create a ScreenScraperService instance for integration testing."""
        return ScreenScraperService()

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_get_game_info_by_crc_real_api(
        self, service, mock_ctx_aiohttp_session
    ):
        """Test get_game_info with CRC using real API call."""
        with patch(
            "adapters.services.screenscraper.ctx_aiohttp_session",
            mock_ctx_aiohttp_session,
        ):
            result = await service.get_game_info(crc="abc123", system_id=1)

        # Verify response structure (might be None if game not found)
        if result is not None:
            assert "id" in result
            assert "noms" in result

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_get_game_info_by_game_id_real_api(
        self, service, mock_ctx_aiohttp_session
    ):
        """Test get_game_info with game ID using real API call."""
        with patch(
            "adapters.services.screenscraper.ctx_aiohttp_session",
            mock_ctx_aiohttp_session,
        ):
            result = await service.get_game_info(game_id=1)

        # Verify response structure
        if result is not None:
            assert "id" in result
            assert "noms" in result
            assert "systeme" in result

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_search_games_real_api(self, service, mock_ctx_aiohttp_session):
        """Test search_games with real API call."""
        with patch(
            "adapters.services.screenscraper.ctx_aiohttp_session",
            mock_ctx_aiohttp_session,
        ):
            result = await service.search_games(term="Mario")

        # Verify response structure
        assert isinstance(result, list)
        if result:  # If there are games
            game = result[0]
            assert "id" in game
            assert "noms" in game

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_search_games_with_system_filter_real_api(
        self, service, mock_ctx_aiohttp_session
    ):
        """Test search_games with system filter using real API call."""
        with patch(
            "adapters.services.screenscraper.ctx_aiohttp_session",
            mock_ctx_aiohttp_session,
        ):
            result = await service.search_games(term="Sonic", system_id=1)

        # Verify response structure
        assert isinstance(result, list)
        if result:
            game = result[0]
            assert "id" in game
            assert "noms" in game

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_error_handling_real_api(self, service, mock_ctx_aiohttp_session):
        """Test error handling with real API calls."""
        with patch(
            "adapters.services.screenscraper.ctx_aiohttp_session",
            mock_ctx_aiohttp_session,
        ):
            with patch(
                "adapters.services.screenscraper.SCREENSCRAPER_USER", "invalid_user"
            ):
                with patch(
                    "adapters.services.screenscraper.SCREENSCRAPER_PASSWORD",
                    "invalid_pass",
                ):
                    # This should handle the error gracefully
                    try:
                        result = await service.get_game_info(game_id=INVALID_GAME_ID)
                        # Should either return None or handle auth error
                        assert result is None or isinstance(result, dict)
                    except HTTPException as e:
                        # Should be authentication error
                        assert e.status_code in [401, 503]

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_get_game_info_not_found_real_api(
        self, service, mock_ctx_aiohttp_session
    ):
        """Test get_game_info with non-existent game using real API call."""
        with patch(
            "adapters.services.screenscraper.ctx_aiohttp_session",
            mock_ctx_aiohttp_session,
        ):
            result = await service.get_game_info(
                crc="FFFFFFFFFFFFFFFF", system_id=INVALID_SYSTEM_ID
            )

        # Should return None for non-existent game
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_search_games_no_results_real_api(
        self, service, mock_ctx_aiohttp_session
    ):
        """Test search_games with term that returns no results using real API call."""
        with patch(
            "adapters.services.screenscraper.ctx_aiohttp_session",
            mock_ctx_aiohttp_session,
        ):
            result = await service.search_games(term="ZZZNonexistentGameZZZ")

        # Should return empty list for no results
        assert result == []


# Performance tests
class TestScreenScraperServicePerformance:
    """Performance tests for ScreenScraper service."""

    @pytest.fixture
    def service(self):
        """Create a ScreenScraperService instance for performance testing."""
        return ScreenScraperService()

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, service):
        """Test multiple concurrent API requests."""
        mock_response = {"response": {"jeu": {"id": "1"}}}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            # Run 5 concurrent requests
            tasks = [service.get_game_info(game_id=i) for i in range(1, 6)]
            results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(result is not None for result in results)
        assert len(results) == 5
        assert mock_request.call_count == 5

    @pytest.mark.asyncio
    async def test_request_timeout_handling(self, service):
        """Test handling of request timeouts."""
        mock_session = AsyncMock()

        # Simulate timeout on first call, success on retry
        timeout_error = aiohttp.ServerTimeoutError("Request timeout")
        success_response = MagicMock()
        success_response.json = AsyncMock(return_value={"response": {"jeu": {}}})
        success_response.text = AsyncMock(return_value='{"response": {"jeu": {}}}')
        success_response.raise_for_status.return_value = None

        mock_session.get.side_effect = [timeout_error, success_response]

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            result = await service._request(
                "https://api.screenscraper.fr/api2/jeuInfos.php", request_timeout=1
            )

        assert result == {"response": {"jeu": {}}}
        assert mock_session.get.call_count == 2

    @pytest.mark.asyncio
    async def test_concurrent_search_requests(self, service):
        """Test multiple concurrent search requests."""
        mock_response = {"response": {"jeux": [{"id": "1"}]}}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            # Run 3 concurrent search requests
            tasks = [
                service.search_games(term="Mario"),
                service.search_games(term="Sonic"),
                service.search_games(term="Zelda"),
            ]
            results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(len(result) == 1 for result in results)
        assert len(results) == 3
        assert mock_request.call_count == 3


# Edge case tests
class TestScreenScraperServiceEdgeCases:
    """Edge case tests for ScreenScraper service."""

    @pytest.fixture
    def service(self):
        """Create a ScreenScraperService instance for edge case testing."""
        return ScreenScraperService()

    @pytest.mark.asyncio
    async def test_get_game_info_with_zero_values(self, service):
        """Test get_game_info with zero values."""
        mock_response = {"response": {"jeu": {"id": "0"}}}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_game_info(
                system_id=0,
                rom_size_bytes=0,
                game_id=0,
            )

        assert result is not None
        call_args = mock_request.call_args[0][0]
        assert "systemeid=0" in call_args
        assert "romtaille=0" in call_args
        assert "gameid=0" in call_args

    @pytest.mark.asyncio
    async def test_search_games_empty_term(self, service):
        """Test search_games with empty term."""
        mock_response: dict[str, dict] = {"response": {"jeux": []}}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.search_games(term="")

        assert result == []
        call_args = mock_request.call_args[0][0]
        assert "recherche=" in call_args

    @pytest.mark.asyncio
    async def test_get_game_info_with_special_characters(self, service):
        """Test get_game_info with special characters in parameters."""
        mock_response = {"response": {"jeu": {"id": "1"}}}

        with patch.object(
            service, "_request", return_value=mock_response
        ) as mock_request:
            result = await service.get_game_info(
                rom_name="Test & Game (USA).nes",
                serial_number="NES-T&G-USA",
            )

        assert result is not None
        call_args = mock_request.call_args[0][0]
        # URL should be properly encoded
        assert "romnom=" in call_args
        assert "serialnum=" in call_args

    @pytest.mark.asyncio
    async def test_request_with_custom_timeout(self, service):
        """Test request with custom timeout."""
        mock_session = AsyncMock()
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"response": {}})
        mock_response.text = AsyncMock(return_value='{"response": {}}')
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            result = await service._request(
                "https://api.screenscraper.fr/api2/jeuInfos.php", request_timeout=30
            )

        assert result == {"response": {}}
        # Verify timeout was passed correctly
        call_kwargs = mock_session.get.call_args[1]
        assert call_kwargs["timeout"].total == 30

    @pytest.mark.asyncio
    async def test_login_error_in_retry_attempt(self, service):
        """Test login error detection in retry attempt."""
        mock_session = AsyncMock()

        # First call times out, second call has login error
        timeout_error = aiohttp.ServerTimeoutError("Timeout")
        login_error_response = MagicMock()
        login_error_response.text = AsyncMock(return_value="Erreur de login detected")
        login_error_response.raise_for_status.return_value = None

        mock_session.get.side_effect = [timeout_error, login_error_response]

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            with pytest.raises(HTTPException) as exc_info:
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid ScreenScraper credentials" in exc_info.value.detail
        assert mock_session.get.call_count == 2
