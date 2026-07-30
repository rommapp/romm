import asyncio
import http
import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
import yarl
from fastapi import HTTPException, status

import adapters.services.screenscraper as ss_module
from adapters.services.screenscraper import (
    LOGIN_ERROR_CHECK,
    SS_DEFAULT_MAX_THREADS,
    SS_DEFAULT_MEDIA_TIMEOUT,
    SS_MAX_MEDIA_TIMEOUT,
    SS_UNPACED_REQUESTS_PER_SECOND,
    ScreenScraperRateLimitError,
    ScreenScraperService,
    _loads_lenient,
    auth_middleware,
    get_account_limits,
    is_daily_quota_exhausted,
    is_screenscraper_url,
    media_download_slot,
    media_download_timeout,
    prime_account_limits,
    reset_daily_quota,
    reset_scan_state,
)
from utils.rate_limiter import ConcurrencyLimiter, RateLimiter

INVALID_GAME_ID = 999999
INVALID_SYSTEM_ID = 999999

# Fast enough that the module's pacing never adds real sleeps to a test.
UNTHROTTLED_RATE = 10_000


def _rendered(mock_call) -> str:
    """Render a lazily-formatted log call into the message it would emit."""
    template, *args = mock_call.args
    return template % tuple(args) if args else str(template)


@pytest.fixture(autouse=True)
def _isolate_module_state(monkeypatch):
    """Pacing, thread allowance and account limits all live at module level, so
    isolate them: without this, learned limits leak between tests and the real
    per-minute pacing would sleep between requests."""
    # Reset first: it re-paces the real limiters, which the swap then hides for
    # the duration of the test, so the unthrottled rate survives to the asserts.
    reset_scan_state()
    monkeypatch.setattr(ss_module, "_rate_limiter", RateLimiter(UNTHROTTLED_RATE))
    monkeypatch.setattr(
        ss_module, "_concurrency_limiter", ConcurrencyLimiter(SS_DEFAULT_MAX_THREADS)
    )
    yield
    reset_scan_state()


class TestScreenScraperConstants:
    """Test ScreenScraper constants and configuration."""

    def test_login_error_check_constant(self):
        """Test that LOGIN_ERROR_CHECK constant is defined."""
        assert LOGIN_ERROR_CHECK == "Erreur de login"


class TestAuthMiddleware:
    @patch("adapters.services.screenscraper.SCREENSCRAPER_DEV_ID", "dev_id")
    @patch("adapters.services.screenscraper.SCREENSCRAPER_DEV_PASSWORD", "dev_pass")
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
            "devid": "dev_id",
            "devpassword": "dev_pass",
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

    @patch("adapters.services.screenscraper.SCREENSCRAPER_DEV_ID", None)
    @patch("adapters.services.screenscraper.SCREENSCRAPER_DEV_PASSWORD", None)
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
            "devid": "",
            "devpassword": "",
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

    @pytest.fixture(autouse=True)
    def _reset_daily_quota(self):
        """The daily-quota breaker is module-level state; reset it around each
        test so a tripped breaker can't leak into unrelated tests."""
        reset_daily_quota()
        yield
        reset_daily_quota()

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
    async def test_request_holds_concurrency_slot(self, service, monkeypatch):
        """Test that the request acquires and releases a concurrency slot."""
        import adapters.services.screenscraper as ss_module

        acquire_mock = AsyncMock()
        release_mock = MagicMock()
        monkeypatch.setattr(ss_module._concurrency_limiter, "acquire", acquire_mock)
        monkeypatch.setattr(ss_module._concurrency_limiter, "release", release_mock)

        mock_session = AsyncMock()
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"response": {}})
        mock_response.text = AsyncMock(return_value="{}")
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        acquire_mock.assert_awaited_once()
        release_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_updates_thread_allowance_from_ssuser(self, service):
        """Test that `ssuser.maxthreads` raises the concurrency cap (donor perk)."""
        import adapters.services.screenscraper as ss_module

        assert ss_module._concurrency_limiter.max_concurrency == 1

        mock_session = AsyncMock()
        mock_response = MagicMock()
        mock_response.json = AsyncMock(
            return_value={"response": {"ssuser": {"maxthreads": "5"}}}
        )
        mock_response.text = AsyncMock(return_value="{}")
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert ss_module._concurrency_limiter.max_concurrency == 5

    @pytest.mark.asyncio
    async def test_request_ignores_invalid_maxthreads(self, service):
        """Test that a missing or unparsable `maxthreads` leaves the cap untouched."""
        import adapters.services.screenscraper as ss_module

        mock_session = AsyncMock()
        mock_response = MagicMock()
        mock_response.json = AsyncMock(
            return_value={"response": {"ssuser": {"maxthreads": "not-a-number"}}}
        )
        mock_response.text = AsyncMock(return_value="{}")
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert ss_module._concurrency_limiter.max_concurrency == 1

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
        """A single rate-limit refusal backs off and the retry succeeds."""
        mock_session = AsyncMock()
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"response": {"jeu": {"id": "1"}}})
        mock_response.text = AsyncMock(
            return_value='{"response": {"jeu": {"id": "1"}}}'
        )
        mock_response.raise_for_status.return_value = None
        mock_session.get.side_effect = [
            aiohttp.ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=http.HTTPStatus.TOO_MANY_REQUESTS,
            ),
            mock_response,
        ]

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            with patch("asyncio.sleep") as mock_sleep:
                result = await service._request(
                    "https://api.screenscraper.fr/api2/jeuInfos.php"
                )

        assert result == {"response": {"jeu": {"id": "1"}}}
        assert any(call.args == (2,) for call in mock_sleep.call_args_list)

    @pytest.mark.asyncio
    async def test_repeated_rate_limit_raises_rate_limit_error(self, service):
        """A refusal that survives the retry must surface, not be swallowed into
        an empty response that saves the ROM with no ScreenScraper data."""
        mock_session = AsyncMock()
        mock_session.get.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=http.HTTPStatus.TOO_MANY_REQUESTS,
        )

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            with patch("asyncio.sleep"):
                with pytest.raises(ScreenScraperRateLimitError) as exc_info:
                    await service._request(
                        "https://api.screenscraper.fr/api2/jeuInfos.php"
                    )

        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "rate limit" in exc_info.value.detail.lower()
        assert mock_session.get.call_count == 2
        # The per-minute limit clears on its own, so it must not short-circuit
        # the rest of the scan the way an exhausted daily quota does.
        assert is_daily_quota_exhausted() is False

    @pytest.mark.asyncio
    async def test_request_paces_against_the_rate_limiter(self, service, monkeypatch):
        """Every request reserves a per-minute slot, not just a thread slot."""
        acquire_mock = AsyncMock()
        monkeypatch.setattr(ss_module._rate_limiter, "acquire", acquire_mock)

        mock_session = AsyncMock()
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"response": {}})
        mock_response.text = AsyncMock(return_value="{}")
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        acquire_mock.assert_awaited_once()

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
    async def test_request_blacklisted_raises_403(self, service):
        """Test that HTTP 426 (blacklisted version) raises HTTP 403."""
        mock_session = AsyncMock()
        mock_session.get.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=426
        )
        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            with pytest.raises(HTTPException) as exc_info:
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "blacklisted" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_request_daily_quota_exhausted_raises_429(self, service):
        """Test that HTTP 430 (daily scrape quota) raises HTTP 429."""
        mock_session = AsyncMock()
        mock_session.get.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=430
        )
        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            with pytest.raises(HTTPException) as exc_info:
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "daily scrape quota" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_request_unrecognized_rom_quota_exhausted_raises_429(self, service):
        """Test that HTTP 431 (unrecognized ROM quota) raises HTTP 429."""
        mock_session = AsyncMock()
        mock_session.get.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=431
        )
        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            with pytest.raises(HTTPException) as exc_info:
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "unrecognized" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_request_daily_quota_exhausted_on_retry_raises_429(self, service):
        """Test that HTTP 430 on the retry attempt still raises HTTP 429."""
        mock_session = AsyncMock()
        # First call times out, retry hits the daily quota.
        mock_session.get.side_effect = [
            aiohttp.ServerTimeoutError("Timeout"),
            aiohttp.ClientResponseError(
                request_info=MagicMock(), history=(), status=430
            ),
        ]
        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            with pytest.raises(HTTPException) as exc_info:
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "daily scrape quota" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_request_daily_quota_trips_breaker_and_short_circuits(self, service):
        """A 430 (daily quota) trips the breaker; subsequent requests short-circuit
        without hitting the API, but still raise 429 so callers see the message."""
        mock_session = AsyncMock()
        mock_session.get.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=430
        )
        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            with pytest.raises(HTTPException):
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

            assert is_daily_quota_exhausted() is True
            assert mock_session.get.call_count == 1

            # The breaker is tripped: the next request must not hit the API, but
            # must still raise 429 so manual search surfaces a clear message.
            with pytest.raises(HTTPException) as exc_info:
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "quota exhausted" in exc_info.value.detail
        assert mock_session.get.call_count == 1

    @pytest.mark.asyncio
    async def test_reset_daily_quota_clears_breaker(self, service):
        """reset_daily_quota() re-enables requests after the breaker tripped."""
        mock_session = AsyncMock()
        mock_session.get.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=431
        )
        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            with pytest.raises(HTTPException):
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert is_daily_quota_exhausted() is True

        reset_daily_quota()
        assert is_daily_quota_exhausted() is False

        # After reset, a fresh request reaches the API again.
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"response": {"jeu": {"id": "1"}}})
        mock_response.text = AsyncMock(
            return_value='{"response": {"jeu": {"id": "1"}}}'
        )
        mock_response.raise_for_status.return_value = None
        mock_session.get.side_effect = None
        mock_session.get.return_value = mock_response

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            result = await service._request(
                "https://api.screenscraper.fr/api2/jeuInfos.php"
            )

        assert result == {"response": {"jeu": {"id": "1"}}}

    @pytest.mark.asyncio
    async def test_request_api_offline_raises_503(self, service):
        """Test that HTTP 423 (API offline) raises HTTP 503."""
        mock_session = AsyncMock()
        mock_session.get.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=423
        )
        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            with pytest.raises(HTTPException) as exc_info:
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "offline" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_request_cpu_throttle_returns_empty_dict(self, service):
        """Test that HTTP 401 (server CPU throttle) returns empty dict without retrying."""
        mock_session = AsyncMock()
        mock_session.get.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=http.HTTPStatus.UNAUTHORIZED,
        )
        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            result = await service._request(
                "https://api.screenscraper.fr/api2/jeuInfos.php"
            )

        assert result == {}
        assert mock_session.get.call_count == 1

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


class TestLoadsLenient:
    """Test tolerant parsing of ScreenScraper's occasionally malformed JSON."""

    def test_parses_valid_json(self):
        assert _loads_lenient('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}

    def test_repairs_invalid_backslash_escape(self):
        # ScreenScraper sometimes emits raw backslashes in text fields, which the
        # strict parser rejects with "Invalid \escape".
        raw = '{"synopsis": "path C:\\emu\\games"}'
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw)
        assert _loads_lenient(raw) == {"synopsis": "path C:\\emu\\games"}

    def test_preserves_valid_escapes(self):
        assert _loads_lenient('{"s": "line\\nbreak \\"quoted\\" \\u00e9"}') == {
            "s": 'line\nbreak "quoted" é'
        }


def _ssuser_response(**fields: str) -> dict:
    return {"response": {"ssuser": dict(fields)}}


class TestAccountLimits:
    """ScreenScraper reports the account's allowances on every response; they
    drive pacing, the quota readout and the configuration advisories."""

    def test_parses_every_reported_limit(self):
        ss_module._update_account_limits(
            _ssuser_response(
                maxthreads="5",
                maxrequestspermin="250",
                maxrequestsperday="20000",
                requeststoday="1500",
                maxrequestskoperday="2000",
                requestskotoday="300",
                maxdownloadspeed="40000",
            )
        )

        limits = get_account_limits()
        assert limits is not None
        assert limits.max_threads == 5
        assert limits.max_requests_per_minute == 250
        assert limits.max_requests_per_day == 20000
        assert limits.requests_today == 1500
        assert limits.max_ko_requests_per_day == 2000
        assert limits.ko_requests_today == 300
        assert limits.max_download_speed_kbps == 40000
        assert limits.remaining_requests == 18500
        assert limits.remaining_ko_requests == 1700

    def test_remaining_is_unknown_without_both_counters(self):
        ss_module._update_account_limits(_ssuser_response(requeststoday="1500"))

        limits = get_account_limits()
        assert limits is not None
        assert limits.remaining_requests is None
        assert limits.remaining_ko_requests is None

    def test_remaining_never_goes_negative(self):
        ss_module._update_account_limits(
            _ssuser_response(maxrequestsperday="20000", requeststoday="20500")
        )

        limits = get_account_limits()
        assert limits is not None
        assert limits.remaining_requests == 0

    def test_leaves_pacing_alone_when_no_budget_is_reported(self):
        """The thread count says nothing about the budget: ScreenScraper's
        `threads x 50` documentation is stale, so there is nothing to derive."""
        ss_module._update_account_limits(_ssuser_response(maxthreads="3"))

        assert ss_module._rate_limiter.requests_per_second == pytest.approx(
            UNTHROTTLED_RATE
        )

    def test_uses_a_reported_limit_above_the_documented_budget(self):
        """maxrequestspermin comes back as 1024 x (threads + 1), far above the
        `threads x 50` the FAQ still documents. ScreenScraper confirmed the API
        changed without the docs following, so the reported figure is the one to
        pace against."""
        ss_module._update_account_limits(
            _ssuser_response(maxthreads="9", maxrequestspermin="10240")
        )

        assert ss_module._rate_limiter.requests_per_second == pytest.approx(10240 / 60)

    def test_honours_a_reported_limit_that_is_low(self):
        """A stricter account limit is still respected."""
        ss_module._update_account_limits(
            _ssuser_response(maxthreads="9", maxrequestspermin="100")
        )

        assert ss_module._rate_limiter.requests_per_second == pytest.approx(100 / 60)

    def test_uses_the_reported_limit_when_threads_are_unknown(self):
        ss_module._update_account_limits(_ssuser_response(maxrequestspermin="600"))

        assert ss_module._rate_limiter.requests_per_second == pytest.approx(600 / 60)

    def test_ignores_unparsable_limits(self):
        ss_module._update_account_limits(
            _ssuser_response(maxthreads="0", maxrequestspermin="not-a-number")
        )

        limits = get_account_limits()
        assert limits is not None
        assert limits.max_threads is None
        assert limits.max_requests_per_minute is None
        assert ss_module._concurrency_limiter.max_concurrency == SS_DEFAULT_MAX_THREADS
        assert ss_module._rate_limiter.requests_per_second == pytest.approx(
            UNTHROTTLED_RATE
        )

    def test_ignores_a_response_without_account_info(self):
        ss_module._update_account_limits({"response": {"jeu": {"id": "1"}}})

        assert get_account_limits() is None

    def test_describes_both_daily_quotas(self):
        ss_module._update_account_limits(
            _ssuser_response(
                maxrequestsperday="20000",
                requeststoday="1500",
                maxrequestskoperday="2000",
                requestskotoday="300",
            )
        )

        limits = get_account_limits()
        assert limits is not None
        description = limits.describe()
        assert "18500" in description
        assert "20000" in description
        assert "1700" in description
        assert "2000" in description

    def test_scan_state_reset_returns_pacing_to_the_defaults(self):
        """Priming re-reads the account moments later; until it does, the single
        thread is the guard for whatever account is configured now."""
        ss_module._update_account_limits(
            _ssuser_response(maxthreads="5", maxrequestspermin="250")
        )
        assert ss_module._concurrency_limiter.max_concurrency == 5

        reset_scan_state()

        assert ss_module._concurrency_limiter.max_concurrency == SS_DEFAULT_MAX_THREADS
        assert ss_module._rate_limiter.requests_per_second == pytest.approx(
            SS_UNPACED_REQUESTS_PER_SECOND
        )

    def test_scan_state_reset_drops_stale_quota_counters(self):
        """Daily counters reset overnight, so a new scan must not report
        yesterday's numbers before the first response arrives."""
        ss_module._update_account_limits(
            _ssuser_response(maxrequestsperday="20000", requeststoday="19999")
        )
        assert get_account_limits() is not None

        reset_scan_state()

        assert get_account_limits() is None


class TestPrimingAccountLimits:
    """The limits ride along on every response, but piggybacking on the first
    scan request means the first ROMs are scraped at the default pacing.
    ssuserInfos.php reports them up front and costs no quota."""

    @pytest.fixture(autouse=True)
    def _credentials(self, monkeypatch):
        monkeypatch.setattr(ss_module, "SCREENSCRAPER_USER", "user1")
        monkeypatch.setattr(ss_module, "SCREENSCRAPER_PASSWORD", "pw1")

    def _mock_session(self, payload: dict) -> tuple[MagicMock, MagicMock]:
        session = AsyncMock()
        response = MagicMock()
        response.json = AsyncMock(return_value=payload)
        response.text = AsyncMock(return_value="{}")
        response.raise_for_status.return_value = None
        session.get.return_value = response

        context = MagicMock()
        context.get.return_value = session
        return session, context

    @pytest.mark.asyncio
    async def test_get_user_info_hits_the_account_endpoint(self):
        service = ScreenScraperService()
        with patch.object(
            service, "_request", return_value={"response": {}}
        ) as mock_request:
            await service.get_user_info()

        assert mock_request.call_args[0][0].endswith("ssuserInfos.php")

    @pytest.mark.asyncio
    async def test_priming_applies_the_limits_before_any_rom_is_scraped(self):
        session, context = self._mock_session(
            _ssuser_response(
                maxthreads="5",
                maxrequestspermin="250",
                maxrequestsperday="20000",
                requeststoday="1500",
            )
        )

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            limits = await prime_account_limits()

        assert limits is not None
        assert limits.max_threads == 5
        assert limits.remaining_requests == 18500
        assert ss_module._concurrency_limiter.max_concurrency == 5
        assert ss_module._rate_limiter.requests_per_second == pytest.approx(250 / 60)
        session.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_priming_is_skipped_without_credentials(self, monkeypatch):
        monkeypatch.setattr(ss_module, "SCREENSCRAPER_USER", "")
        monkeypatch.setattr(ss_module, "SCREENSCRAPER_PASSWORD", "")
        session, context = self._mock_session(_ssuser_response(maxthreads="5"))

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            assert await prime_account_limits() is None

        session.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_priming_never_fails_the_scan(self, monkeypatch):
        """A scan must still run when the account lookup is refused."""
        mock_log = MagicMock()
        monkeypatch.setattr(ss_module, "log", mock_log)

        session = AsyncMock()
        session.get.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=423
        )
        context = MagicMock()
        context.get.return_value = session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            assert await prime_account_limits() is None

        assert mock_log.warning.called


class TestQuotaWarnings:
    @pytest.fixture
    def mock_log(self, monkeypatch):
        mock_log = MagicMock()
        monkeypatch.setattr(ss_module, "log", mock_log)
        return mock_log

    def test_warns_when_the_daily_quota_is_nearly_exhausted(self, mock_log):
        ss_module._update_account_limits(
            _ssuser_response(maxrequestsperday="20000", requeststoday="19500")
        )

        messages = [_rendered(call) for call in mock_log.warning.call_args_list]
        assert any("500" in message for message in messages)

    def test_warns_when_the_unrecognized_rom_quota_is_nearly_exhausted(self, mock_log):
        ss_module._update_account_limits(
            _ssuser_response(maxrequestskoperday="2000", requestskotoday="1950")
        )

        messages = [_rendered(call) for call in mock_log.warning.call_args_list]
        assert any("unrecognized" in message.lower() for message in messages)

    def test_does_not_warn_with_quota_to_spare(self, mock_log):
        ss_module._update_account_limits(
            _ssuser_response(
                maxrequestsperday="20000",
                requeststoday="1500",
                maxrequestskoperday="2000",
                requestskotoday="100",
            )
        )

        assert mock_log.warning.call_count == 0

    def test_warns_once_per_scan(self, mock_log):
        payload = _ssuser_response(maxrequestsperday="20000", requeststoday="19500")

        ss_module._update_account_limits(payload)
        ss_module._update_account_limits(payload)
        assert mock_log.warning.call_count == 1

        reset_scan_state()
        ss_module._update_account_limits(payload)
        assert mock_log.warning.call_count == 2


class TestWorkerAdvisory:
    """SCAN_WORKERS bounds how many ScreenScraper requests can be in flight, so a
    mismatch with the account's thread allowance is worth pointing out."""

    @pytest.fixture
    def mock_log(self, monkeypatch):
        mock_log = MagicMock()
        monkeypatch.setattr(ss_module, "log", mock_log)
        return mock_log

    def test_hints_when_scan_workers_wastes_the_allowance(self, mock_log, monkeypatch):
        monkeypatch.setattr(ss_module, "SCAN_WORKERS", 1)

        ss_module._update_account_limits(_ssuser_response(maxthreads="5"))

        messages = [_rendered(call) for call in mock_log.info.call_args_list]
        assert any("SCAN_WORKERS" in message and "5" in message for message in messages)

    def test_notes_when_scan_workers_exceeds_the_allowance(self, mock_log, monkeypatch):
        monkeypatch.setattr(ss_module, "SCAN_WORKERS", 8)

        ss_module._update_account_limits(_ssuser_response(maxthreads="2"))

        messages = [_rendered(call) for call in mock_log.info.call_args_list]
        assert any("queue" in message for message in messages)

    def test_silent_when_scan_workers_matches_the_allowance(
        self, mock_log, monkeypatch
    ):
        monkeypatch.setattr(ss_module, "SCAN_WORKERS", 4)

        ss_module._update_account_limits(_ssuser_response(maxthreads="4"))

        messages = [_rendered(call) for call in mock_log.info.call_args_list]
        assert not any("SCAN_WORKERS" in message for message in messages)

    def test_advised_once_per_scan(self, mock_log, monkeypatch):
        monkeypatch.setattr(ss_module, "SCAN_WORKERS", 1)
        payload = _ssuser_response(maxthreads="5")

        ss_module._update_account_limits(payload)
        ss_module._update_account_limits(payload)
        advisories = [
            message
            for message in (_rendered(call) for call in mock_log.info.call_args_list)
            if "SCAN_WORKERS" in message
        ]
        assert len(advisories) == 1

        reset_scan_state()
        ss_module._update_account_limits(payload)
        advisories = [
            message
            for message in (_rendered(call) for call in mock_log.info.call_args_list)
            if "SCAN_WORKERS" in message
        ]
        assert len(advisories) == 2


class TestMediaDownloads:
    """Media downloads hit the same account allowances as API calls, so they
    have to share the limiters instead of bypassing them."""

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://www.screenscraper.fr/image.php?gameid=1", True),
            ("https://screenscraper.fr/media.php", True),
            ("https://SCREENSCRAPER.FR/media.php", True),
            ("https://screenscraper.fr.evil.example/media.php", False),
            ("https://cdn.example.com/cover.png", False),
            ("", False),
            (None, False),
        ],
    )
    def test_recognizes_screenscraper_urls(self, url, expected):
        assert is_screenscraper_url(url) is expected

    @pytest.mark.asyncio
    async def test_holds_a_thread_slot_for_screenscraper_media(self):
        async with media_download_slot(
            "https://www.screenscraper.fr/image.php?gameid=1"
        ) as timeout:
            assert ss_module._concurrency_limiter.in_flight == 1
            assert timeout == SS_DEFAULT_MEDIA_TIMEOUT

        assert ss_module._concurrency_limiter.in_flight == 0

    @pytest.mark.asyncio
    async def test_releases_the_slot_when_the_download_fails(self):
        with pytest.raises(RuntimeError):
            async with media_download_slot("https://www.screenscraper.fr/image.php"):
                raise RuntimeError("connection reset")

        assert ss_module._concurrency_limiter.in_flight == 0

    @pytest.mark.asyncio
    async def test_paces_screenscraper_media_downloads(self, monkeypatch):
        acquire_mock = AsyncMock()
        monkeypatch.setattr(ss_module._rate_limiter, "acquire", acquire_mock)

        async with media_download_slot("https://www.screenscraper.fr/image.php"):
            pass

        acquire_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_leaves_other_hosts_alone(self, monkeypatch):
        acquire_mock = AsyncMock()
        monkeypatch.setattr(ss_module._rate_limiter, "acquire", acquire_mock)

        async with media_download_slot("https://cdn.example.com/cover.png") as timeout:
            assert ss_module._concurrency_limiter.in_flight == 0
            assert timeout == SS_DEFAULT_MEDIA_TIMEOUT

        acquire_mock.assert_not_awaited()

    def test_timeout_defaults_without_a_reported_speed(self):
        assert media_download_timeout() == SS_DEFAULT_MEDIA_TIMEOUT

    def test_timeout_grows_for_a_throttled_account(self):
        ss_module._update_account_limits(_ssuser_response(maxdownloadspeed="128"))

        timeout = media_download_timeout()
        assert SS_DEFAULT_MEDIA_TIMEOUT < timeout <= SS_MAX_MEDIA_TIMEOUT

    def test_timeout_is_capped_for_the_slowest_accounts(self):
        ss_module._update_account_limits(_ssuser_response(maxdownloadspeed="16"))

        assert media_download_timeout() == SS_MAX_MEDIA_TIMEOUT

    def test_timeout_stays_at_the_floor_for_fast_accounts(self):
        ss_module._update_account_limits(_ssuser_response(maxdownloadspeed="40000"))

        assert media_download_timeout() == SS_DEFAULT_MEDIA_TIMEOUT
