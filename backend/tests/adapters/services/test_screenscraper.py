import asyncio
import http
import json
import time
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
    SS_QUOTA_TRIP_THRESHOLD,
    SS_UNPACED_REQUESTS_PER_SECOND,
    ScreenScraperCredentialsError,
    ScreenScraperRateLimitError,
    ScreenScraperService,
    SSCredentialSet,
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

# What ScreenScraper answers a rejected credential set with, verbatim. The
# account endpoint blames the account whichever set is at fault; only a
# scraping endpoint names the developer credentials.
SS_LOGIN_ERROR_BODY = "Erreur de login : Vérifier les identifiants utilisateurs !"
SS_DEV_ERROR_BODY = "Erreur de login : Vérifier vos identifiants développeur !"
ACCOUNT_URL = "https://api.screenscraper.fr/api2/ssuserInfos.php"


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

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "RomM developer credentials" in exc_info.value.detail

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
    async def test_request_submission_limit_is_an_empty_response(self, service):
        """HTTP 431 means this ROM did not match and the daily cap on proposing
        unknown ROMs is reached. Scraping is unaffected, so it is a not-found."""
        mock_session = AsyncMock()
        mock_session.get.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=431
        )
        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            result = await service._request(
                "https://api.screenscraper.fr/api2/jeuInfos.php"
            )

        assert result == {}
        assert is_daily_quota_exhausted() is False

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
        """Repeated 430s (daily quota) trip the breaker; subsequent requests
        short-circuit without hitting the API, but still raise 429 so callers see
        the message."""
        mock_session = AsyncMock()
        mock_session.get.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=430
        )
        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            for _ in range(SS_QUOTA_TRIP_THRESHOLD):
                with pytest.raises(HTTPException):
                    await service._request(
                        "https://api.screenscraper.fr/api2/jeuInfos.php"
                    )

            assert is_daily_quota_exhausted() is True
            assert mock_session.get.call_count == SS_QUOTA_TRIP_THRESHOLD

            # The breaker is tripped: the next request must not hit the API, but
            # must still raise 429 so manual search surfaces a clear message.
            with pytest.raises(HTTPException) as exc_info:
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "daily scrape quota" in exc_info.value.detail
        assert mock_session.get.call_count == SS_QUOTA_TRIP_THRESHOLD

    @pytest.mark.asyncio
    async def test_reset_daily_quota_clears_breaker(self, service):
        """reset_daily_quota() re-enables requests after the breaker tripped."""
        mock_session = AsyncMock()
        mock_session.get.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=430
        )
        mock_context = MagicMock()
        mock_context.get.return_value = mock_session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", mock_context):
            for _ in range(SS_QUOTA_TRIP_THRESHOLD):
                with pytest.raises(HTTPException):
                    await service._request(
                        "https://api.screenscraper.fr/api2/jeuInfos.php"
                    )

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

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "RomM developer credentials" in exc_info.value.detail
        assert mock_session.get.call_count == 2


class TestCredentialErrors:
    """ScreenScraper refuses a bad credential set with HTTP 403. RomM has to say
    which set, rather than the bare "403, message='Forbidden'" that sends users
    looking at their quota.

    Only the account endpoint checks the account password, so a refusal from a
    scraping endpoint is always about RomM's own credentials, whatever the body
    happens to say."""

    @pytest.fixture
    def service(self):
        return ScreenScraperService()

    def _forbidden_response(self, body: str = SS_LOGIN_ERROR_BODY) -> MagicMock:
        """A response whose body carries the login error, as a 403 does."""
        response = MagicMock()
        response.text = AsyncMock(return_value=body)
        response.json = AsyncMock(return_value={})
        response.raise_for_status.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=http.HTTPStatus.FORBIDDEN,
            message="Forbidden",
        )
        return response

    def _session(self, *responses) -> tuple[AsyncMock, MagicMock]:
        session = AsyncMock()
        if len(responses) == 1:
            session.get.return_value = responses[0]
        else:
            session.get.side_effect = list(responses)

        context = MagicMock()
        context.get.return_value = session
        return session, context

    @pytest.mark.asyncio
    async def test_the_account_endpoint_reports_the_account_sign_in(self, service):
        _, context = self._session(self._forbidden_response())

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            with pytest.raises(ScreenScraperCredentialsError) as exc_info:
                await service._request(ACCOUNT_URL)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.credential_set is SSCredentialSet.USER
        assert "SCREENSCRAPER_USER" in exc_info.value.detail
        assert "SCREENSCRAPER_PASSWORD" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_a_scraping_endpoint_reports_romms_own_credentials(self, service):
        _, context = self._session(self._forbidden_response(SS_DEV_ERROR_BODY))

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            with pytest.raises(ScreenScraperCredentialsError) as exc_info:
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert exc_info.value.credential_set is SSCredentialSet.DEVELOPER
        assert "RomM developer credentials" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_the_developer_credentials_are_never_named(self, service):
        """Their values are only semi-protected, so nothing sends an end user
        looking for them."""
        _, context = self._session(self._forbidden_response(SS_DEV_ERROR_BODY))

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            with pytest.raises(ScreenScraperCredentialsError) as exc_info:
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert "SCREENSCRAPER_DEV_ID" not in exc_info.value.detail
        assert "SCREENSCRAPER_DEV_PASSWORD" not in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_a_scraping_refusal_is_not_blamed_on_the_account(self, service):
        """ScreenScraper says "utilisateurs" from endpoints that never check the
        account password, so the endpoint settles it rather than the wording."""
        _, context = self._session(self._forbidden_response())

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            with pytest.raises(ScreenScraperCredentialsError) as exc_info:
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert exc_info.value.credential_set is SSCredentialSet.DEVELOPER

    @pytest.mark.asyncio
    async def test_the_body_is_read_before_the_status_is_raised(self, service):
        """The regression: the login-error check sat after raise_for_status(), so
        it could never match the 403 it was written for."""
        response = self._forbidden_response()
        _, context = self._session(response)

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            with pytest.raises(ScreenScraperCredentialsError) as exc_info:
                await service._request(ACCOUNT_URL)

        response.text.assert_awaited()
        # ScreenScraper's own wording, carried through under RomM's summary.
        assert "identifiants utilisateurs" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_credentials_are_masked_in_the_reported_message(self, service):
        """The message reaches the caller, and the credentials ride in the query
        string ScreenScraper is free to quote back."""
        _, context = self._session(
            self._forbidden_response(
                "Erreur de login : ssid=user1&sspassword=hunter2&devpassword=s3cret"
            )
        )

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            with pytest.raises(ScreenScraperCredentialsError) as exc_info:
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert "hunter2" not in exc_info.value.detail
        assert "s3cret" not in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_forbidden_without_a_body_still_names_a_set(self, service):
        _, context = self._session(self._forbidden_response(""))

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            with pytest.raises(ScreenScraperCredentialsError) as exc_info:
                await service._request(ACCOUNT_URL)

        assert "SCREENSCRAPER_USER" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_rejected_credentials_are_not_retried(self, service):
        """Nothing about a wrong password clears on a second attempt."""
        session, context = self._session(self._forbidden_response())

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            with pytest.raises(ScreenScraperCredentialsError):
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert session.get.call_count == 1

    @pytest.mark.asyncio
    async def test_forbidden_on_the_retry_attempt_is_reported(self, service):
        session, context = self._session(
            aiohttp.ServerTimeoutError("Timeout"), self._forbidden_response()
        )

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            with pytest.raises(ScreenScraperCredentialsError):
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert session.get.call_count == 2

    @pytest.mark.asyncio
    async def test_later_requests_short_circuit(self, service):
        """Every remaining ROM would be refused the same way, so stop asking."""
        session, context = self._session(self._forbidden_response())

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            with pytest.raises(ScreenScraperCredentialsError):
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")
            with pytest.raises(ScreenScraperCredentialsError):
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert session.get.call_count == 1

    @pytest.mark.asyncio
    async def test_the_failure_is_logged_once(self, service, monkeypatch):
        mock_log = MagicMock()
        monkeypatch.setattr(ss_module, "log", mock_log)
        _, context = self._session(self._forbidden_response())

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            for _ in range(2):
                with pytest.raises(ScreenScraperCredentialsError):
                    await service._request(
                        "https://api.screenscraper.fr/api2/jeuInfos.php"
                    )

        assert mock_log.error.call_count == 1
        assert "RomM developer credentials" in _rendered(mock_log.error.call_args)

    @pytest.mark.asyncio
    async def test_a_new_scan_asks_again(self, service):
        """Credentials are read at startup, so a restart is what clears this."""
        _, context = self._session(self._forbidden_response())

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            with pytest.raises(ScreenScraperCredentialsError):
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        reset_scan_state()

        ok_response = MagicMock()
        ok_response.text = AsyncMock(return_value="{}")
        ok_response.json = AsyncMock(return_value={"response": {}})
        ok_response.raise_for_status.return_value = None
        session, context = self._session(ok_response)

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            assert await service._request(
                "https://api.screenscraper.fr/api2/jeuInfos.php"
            ) == {"response": {}}

        session.get.assert_called_once()


class TestSubmissionLimit:
    """HTTP 431 is two things at once: this ROM did not match, and the account has
    proposed its daily maximum of unknown ROMs to ScreenScraper's moderation
    queue. Only the first affects the scan, so it is a not-found that costs a
    contribution, never a reason to stop scraping."""

    @pytest.fixture
    def service(self):
        return ScreenScraperService()

    def _session(self, *responses) -> tuple[AsyncMock, MagicMock]:
        session = AsyncMock()
        session.get.side_effect = list(responses)
        context = MagicMock()
        context.get.return_value = session
        return session, context

    def _refused(self) -> aiohttp.ClientResponseError:
        return aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=431
        )

    def _matched(self) -> MagicMock:
        response = MagicMock()
        response.text = AsyncMock(return_value='{"response": {"jeu": {"id": "1"}}}')
        response.json = AsyncMock(return_value={"response": {"jeu": {"id": "1"}}})
        response.raise_for_status.return_value = None
        return response

    @pytest.mark.asyncio
    async def test_the_next_rom_still_scrapes(self, service):
        """The whole defect in one test: an unmatched ROM must not cost the scan
        every ROM that would have matched."""
        session, context = self._session(self._refused(), self._matched())

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            assert (
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")
                == {}
            )
            assert await service._request(
                "https://api.screenscraper.fr/api2/jeuInfos.php"
            ) == {"response": {"jeu": {"id": "1"}}}

        assert session.get.call_count == 2
        assert ss_module.is_breaker_tripped() is False

    @pytest.mark.asyncio
    async def test_the_lost_contribution_is_reported_once(self, service, monkeypatch):
        """Every unmatched ROM in a scan gets the same 431, so say it once."""
        mock_log = MagicMock()
        monkeypatch.setattr(ss_module, "log", mock_log)
        session, context = self._session(*(self._refused() for _ in range(4)))

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            for _ in range(4):
                assert (
                    await service._request(
                        "https://api.screenscraper.fr/api2/jeuInfos.php"
                    )
                    == {}
                )

        assert session.get.call_count == 4
        assert mock_log.warning.call_count == 0
        assert mock_log.info.call_count == 1
        assert "submitting unknown ROMs" in _rendered(mock_log.info.call_args)

    @pytest.mark.asyncio
    async def test_a_new_scan_reports_it_again(self, service, monkeypatch):
        mock_log = MagicMock()
        monkeypatch.setattr(ss_module, "log", mock_log)
        _, context = self._session(self._refused(), self._refused())

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")
            reset_scan_state()
            await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert mock_log.info.call_count == 2

    @pytest.mark.asyncio
    async def test_the_submission_limit_never_counts_toward_the_breaker(self, service):
        """A library of unmatched ROMs would otherwise arm the scrape breaker."""
        _, context = self._session(*(self._refused() for _ in range(5)))

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            for _ in range(5):
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert ss_module._state.daily_quota_errors == 0
        assert is_daily_quota_exhausted() is False


class TestDailyQuotaBreaker:
    """HTTP 430 means the daily scrape allowance really is spent, so the breaker
    earns its place: every remaining ROM would otherwise cost a serialized round
    trip to be told the same thing. It has to be recoverable, though, because the
    web process never starts a scan and so never resets it."""

    @pytest.fixture
    def service(self):
        return ScreenScraperService()

    def _session(self, *responses) -> tuple[AsyncMock, MagicMock]:
        session = AsyncMock()
        session.get.side_effect = list(responses)
        context = MagicMock()
        context.get.return_value = session
        return session, context

    def _refused(self) -> aiohttp.ClientResponseError:
        return aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=430
        )

    def _account(self, **fields: str) -> MagicMock:
        payload = _ssuser_response(**fields)
        response = MagicMock()
        response.text = AsyncMock(return_value=json.dumps(payload))
        response.json = AsyncMock(return_value=payload)
        response.raise_for_status.return_value = None
        return response

    def _forbidden(self) -> MagicMock:
        """A refused credential set, the way the account endpoint answers one."""
        response = MagicMock()
        response.text = AsyncMock(return_value=SS_LOGIN_ERROR_BODY)
        response.json = AsyncMock(return_value={})
        response.raise_for_status.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=http.HTTPStatus.FORBIDDEN,
            message="Forbidden",
        )
        return response

    def _due_for_a_recheck(self) -> None:
        ss_module._state.quota_recheck_at = time.monotonic() - 1

    async def _arm(self, service, context) -> None:
        for _ in range(SS_QUOTA_TRIP_THRESHOLD):
            with pytest.raises(HTTPException):
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")
        assert is_daily_quota_exhausted() is True

    @pytest.mark.asyncio
    async def test_one_refusal_is_not_enough(self, service):
        """ScreenScraper answers 430 for reasons that do not survive a retry, and
        one of them must not cost the scan the provider."""
        session, context = self._session(self._refused(), self._account())

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            with pytest.raises(HTTPException):
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

            assert is_daily_quota_exhausted() is False

            await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert session.get.call_count == 2

    @pytest.mark.asyncio
    async def test_a_response_in_between_clears_the_count(self, service):
        _, context = self._session(self._refused(), self._account(), self._refused())

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            with pytest.raises(HTTPException):
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")
            await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")
            with pytest.raises(HTTPException):
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert is_daily_quota_exhausted() is False

    @pytest.mark.asyncio
    async def test_the_submission_limit_does_not_count(self, service):
        """A scan interleaves unmatched ROMs with refused ones; only the refusals
        of the scrape allowance may arm the breaker."""
        unmatched = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=431
        )
        _, context = self._session(self._refused(), unmatched, self._refused())

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            with pytest.raises(HTTPException):
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")
            await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")
            with pytest.raises(HTTPException):
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert is_daily_quota_exhausted() is True

    @pytest.mark.asyncio
    async def test_a_refusal_on_the_retry_leg_counts(self, service):
        """The first attempt can time out, and the retry is where the wall shows."""
        _, context = self._session(
            aiohttp.ServerTimeoutError("Timeout"),
            self._refused(),
            aiohttp.ServerTimeoutError("Timeout"),
            self._refused(),
        )

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            for _ in range(SS_QUOTA_TRIP_THRESHOLD):
                with pytest.raises(HTTPException):
                    await service._request(
                        "https://api.screenscraper.fr/api2/jeuInfos.php"
                    )

        assert is_daily_quota_exhausted() is True

    @pytest.mark.asyncio
    async def test_simultaneous_refusals_are_one_wall(self, service, monkeypatch):
        """An account with a thread allowance has that many requests in flight
        when the quota runs out. They all come back 430, but they are the same
        refusal seen N times, so a threshold above one has to survive them."""
        in_flight = SS_QUOTA_TRIP_THRESHOLD + 2
        monkeypatch.setattr(
            ss_module, "_concurrency_limiter", ConcurrencyLimiter(in_flight)
        )

        # Hold every request until they are all in flight, so the refusals really
        # do overlap rather than arriving one after another.
        all_sent = asyncio.Event()
        sent = 0

        async def refuse_once(*args, **kwargs):
            nonlocal sent
            sent += 1
            if sent == in_flight:
                all_sent.set()
            await all_sent.wait()
            raise self._refused()

        session = AsyncMock()
        session.get.side_effect = refuse_once
        context = MagicMock()
        context.get.return_value = session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            results = await asyncio.gather(
                *(
                    service._request("https://api.screenscraper.fr/api2/jeuInfos.php")
                    for _ in range(in_flight)
                ),
                return_exceptions=True,
            )

        assert all(isinstance(result, HTTPException) for result in results)
        assert ss_module._state.daily_quota_errors == 1
        assert is_daily_quota_exhausted() is False

    @pytest.mark.asyncio
    async def test_it_is_reported_once(self, service, monkeypatch):
        mock_log = MagicMock()
        monkeypatch.setattr(ss_module, "log", mock_log)
        _, context = self._session(*(self._refused() for _ in range(4)))

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            await self._arm(service, context)
            with pytest.raises(HTTPException):
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        messages = [_rendered(call) for call in mock_log.warning.call_args_list]
        assert sum("pausing ScreenScraper" in message for message in messages) == 1

    @pytest.mark.asyncio
    async def test_it_recovers_once_the_account_has_room_again(self, service):
        """The web process never starts a scan, so nothing else will ever clear
        this. The account endpoint costs no quota, which is what makes the
        re-check affordable."""
        _, context = self._session(
            *(self._refused() for _ in range(SS_QUOTA_TRIP_THRESHOLD))
        )

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            await self._arm(service, context)

        session, context = self._session(
            self._account(maxrequestsperday="20000", requeststoday="10"),
            self._account(maxrequestsperday="20000", requeststoday="11"),
        )
        self._due_for_a_recheck()

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            assert await service._request(
                "https://api.screenscraper.fr/api2/jeuInfos.php"
            ) == _ssuser_response(maxrequestsperday="20000", requeststoday="11")

        assert is_daily_quota_exhausted() is False
        # The re-check itself, then the request that was asking.
        assert session.get.call_count == 2
        assert session.get.call_args_list[0][0][0].endswith("ssuserInfos.php")

    @pytest.mark.asyncio
    async def test_it_stays_armed_while_the_allowance_is_still_spent(
        self, service, monkeypatch
    ):
        mock_log = MagicMock()
        monkeypatch.setattr(ss_module, "log", mock_log)
        _, context = self._session(
            *(self._refused() for _ in range(SS_QUOTA_TRIP_THRESHOLD))
        )

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            await self._arm(service, context)

        session, context = self._session(
            self._account(maxrequestsperday="20000", requeststoday="20000")
        )
        self._due_for_a_recheck()

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            with pytest.raises(HTTPException):
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert is_daily_quota_exhausted() is True
        assert session.get.call_count == 1
        messages = [_rendered(call) for call in mock_log.warning.call_args_list]
        assert sum("pausing ScreenScraper" in message for message in messages) == 1

    @pytest.mark.asyncio
    async def test_a_re_check_is_claimed_before_it_is_made(self, service):
        """Concurrent short-circuiting requests must not all probe at once."""
        _, context = self._session(
            *(self._refused() for _ in range(SS_QUOTA_TRIP_THRESHOLD))
        )

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            await self._arm(service, context)

        session, context = self._session(
            self._account(maxrequestsperday="20000", requeststoday="20000")
        )
        self._due_for_a_recheck()

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            results = await asyncio.gather(
                *(
                    service._request("https://api.screenscraper.fr/api2/jeuInfos.php")
                    for _ in range(4)
                ),
                return_exceptions=True,
            )

        assert all(isinstance(result, HTTPException) for result in results)
        assert session.get.call_count == 1

    @pytest.mark.asyncio
    async def test_a_failed_re_check_never_reaches_the_caller(self, service):
        """A re-check that times out must not turn a short-circuit into a crash,
        and must not wedge the breaker either."""
        _, context = self._session(
            *(self._refused() for _ in range(SS_QUOTA_TRIP_THRESHOLD))
        )

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            await self._arm(service, context)

        _, context = self._session(aiohttp.ServerTimeoutError("Timeout"))
        self._due_for_a_recheck()

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            with pytest.raises(HTTPException) as exc_info:
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert is_daily_quota_exhausted() is True
        assert ss_module._state.quota_recheck_at is not None

    @pytest.mark.asyncio
    async def test_a_connection_error_on_the_re_check_is_survivable(self, service):
        _, context = self._session(
            *(self._refused() for _ in range(SS_QUOTA_TRIP_THRESHOLD))
        )

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            await self._arm(service, context)

        _, context = self._session(aiohttp.ClientConnectionError("nope"))
        self._due_for_a_recheck()

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            with pytest.raises(HTTPException):
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert is_daily_quota_exhausted() is True

    @pytest.mark.asyncio
    async def test_a_re_check_without_a_reading_stays_armed(self, service):
        """ScreenScraper answers 200 with a body it could not fill. The limits it
        leaves behind are the ones from before the wall, so they still show
        headroom: resuming on them would claim a recovery that never happened."""
        _, context = self._session(
            self._account(maxrequestsperday="20000", requeststoday="10"),
            *(self._refused() for _ in range(SS_QUOTA_TRIP_THRESHOLD)),
        )

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")
            await self._arm(service, context)

        empty = MagicMock()
        empty.text = AsyncMock(return_value='{"response": {}}')
        empty.json = AsyncMock(return_value={"response": {}})
        empty.raise_for_status.return_value = None
        session, context = self._session(empty)
        self._due_for_a_recheck()

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            with pytest.raises(HTTPException):
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert is_daily_quota_exhausted() is True
        # The probe went out, but the caller's request did not follow it.
        assert session.get.call_count == 1

    @pytest.mark.asyncio
    async def test_a_refusal_that_keeps_not_sticking_is_reported_once(
        self, service, monkeypatch
    ):
        """A response clears the count, so a 430 that never survives a retry would
        otherwise warn on every ROM in the library."""
        mock_log = MagicMock()
        monkeypatch.setattr(ss_module, "log", mock_log)
        responses = []
        for _ in range(6):
            responses += [self._refused(), self._account()]
        _, context = self._session(*responses)

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            for _ in range(6):
                with pytest.raises(HTTPException):
                    await service._request(
                        "https://api.screenscraper.fr/api2/jeuInfos.php"
                    )
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert is_daily_quota_exhausted() is False
        messages = [_rendered(call) for call in mock_log.warning.call_args_list]
        assert sum("refused a request" in message for message in messages) == 1

    @pytest.mark.asyncio
    async def test_a_refused_re_check_never_arms_the_credentials_breaker(self, service):
        """ScreenScraper refuses a developer id it accepted a minute earlier, and
        nothing outside a scan clears the credentials breaker. A probe that armed
        it would wedge the provider harder than the quota breaker it is checking."""
        _, context = self._session(
            *(self._refused() for _ in range(SS_QUOTA_TRIP_THRESHOLD))
        )

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            await self._arm(service, context)

        _, context = self._session(self._forbidden())
        self._due_for_a_recheck()

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            with pytest.raises(HTTPException) as exc_info:
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        # The caller hears about the quota, not the probe's refusal.
        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert ss_module._state.credentials_rejected is None

        # And once the allowance comes back, ScreenScraper is usable again.
        session, context = self._session(
            self._account(maxrequestsperday="20000", requeststoday="10"),
            self._account(maxrequestsperday="20000", requeststoday="11"),
        )
        self._due_for_a_recheck()

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert is_daily_quota_exhausted() is False
        assert session.get.call_count == 2

    @pytest.mark.asyncio
    async def test_a_re_check_leaves_a_refused_credential_set_refused(self, service):
        """Restoring what the probe found must not hand an already-refused set a
        second chance either."""
        _, context = self._session(
            *(self._refused() for _ in range(SS_QUOTA_TRIP_THRESHOLD))
        )

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            await self._arm(service, context)

        ss_module._state.credentials_rejected = SSCredentialSet.DEVELOPER
        _, context = self._session(self._forbidden())
        self._due_for_a_recheck()

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            # The quota guard runs first, so that is the refusal the caller sees.
            with pytest.raises(HTTPException) as exc_info:
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")

        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert ss_module._state.credentials_rejected is SSCredentialSet.DEVELOPER

    @pytest.mark.asyncio
    async def test_the_credentials_breaker_still_stands_on_its_own(self, service):
        """Clearing the quota breaker must not hand a refused credential set a
        second chance: nothing but a restart fixes that one."""
        _, context = self._session(
            *(self._refused() for _ in range(SS_QUOTA_TRIP_THRESHOLD))
        )

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            await self._arm(service, context)

        ss_module._state.credentials_rejected = SSCredentialSet.DEVELOPER
        reset_daily_quota()

        assert is_daily_quota_exhausted() is False
        assert ss_module.is_breaker_tripped() is True

    def test_a_new_scan_clears_everything_the_breaker_tracks(self):
        ss_module._state.daily_quota_errors = 1
        ss_module._state.daily_quota_exhausted = True
        ss_module._state.quota_recheck_at = time.monotonic()
        ss_module._state.logged_submission_limit_notice = True
        ss_module._state.logged_low_ko_quota_notice = True
        ss_module._state.logged_quota_refusal_notice = True

        reset_scan_state()

        assert ss_module._state.daily_quota_errors == 0
        assert ss_module._state.daily_quota_exhausted is False
        assert ss_module._state.quota_recheck_at is None
        assert ss_module._state.logged_submission_limit_notice is False
        assert ss_module._state.logged_low_ko_quota_notice is False
        assert ss_module._state.logged_quota_refusal_notice is False


class TestApiClosedForAccount:
    """ScreenScraper's error table gives HTTP 401 two halves: the description is
    "API fermé pour les non membres ou les membres inactifs" and the cause is
    "Le Serveur est saturé (utilisation CPU>60%)". Reporting either one alone
    sends the reader looking in the wrong place."""

    @pytest.fixture
    def service(self):
        return ScreenScraperService()

    def _unauthorized_session(self) -> MagicMock:
        session = AsyncMock()
        session.get.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=http.HTTPStatus.UNAUTHORIZED,
        )
        context = MagicMock()
        context.get.return_value = session
        return context

    @pytest.mark.asyncio
    async def test_unauthorized_describes_a_closed_account(self, service, monkeypatch):
        mock_log = MagicMock()
        monkeypatch.setattr(ss_module, "log", mock_log)

        with patch(
            "adapters.services.screenscraper.ctx_aiohttp_session",
            self._unauthorized_session(),
        ):
            assert (
                await service._request("https://api.screenscraper.fr/api2/jeuInfos.php")
                == {}
            )

        messages = [_rendered(call).lower() for call in mock_log.warning.call_args_list]
        assert any("inactive" in message and "cpu" in message for message in messages)


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

    @pytest.mark.asyncio
    async def test_priming_warns_when_the_lookup_answers_nothing(self, monkeypatch):
        """The errors that are swallowed into an empty response left the scan with
        no limits and no warning: complete silence."""
        mock_log = MagicMock()
        monkeypatch.setattr(ss_module, "log", mock_log)

        session = AsyncMock()
        session.get.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=http.HTTPStatus.BAD_REQUEST,
        )
        context = MagicMock()
        context.get.return_value = session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            assert await prime_account_limits() is None

        assert mock_log.warning.called

    @pytest.mark.asyncio
    async def test_priming_reports_rejected_credentials(self, monkeypatch):
        mock_log = MagicMock()
        monkeypatch.setattr(ss_module, "log", mock_log)

        response = MagicMock()
        response.text = AsyncMock(return_value=SS_LOGIN_ERROR_BODY)
        response.json = AsyncMock(return_value={})
        response.raise_for_status.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=http.HTTPStatus.FORBIDDEN,
        )
        session = AsyncMock()
        session.get.return_value = response
        context = MagicMock()
        context.get.return_value = session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            assert await prime_account_limits() is None

        # The full explanation is the error the service already logged; the
        # warning only has to say why no quota readout follows.
        assert "SCREENSCRAPER_USER" in _rendered(mock_log.error.call_args)
        messages = [_rendered(call) for call in mock_log.warning.call_args_list]
        assert any("credentials" in message for message in messages)

    @pytest.mark.parametrize("refused_with", (430, 431))
    @pytest.mark.asyncio
    async def test_priming_never_arms_the_quota_breaker(self, refused_with):
        """The account check reports; only a request the scan actually needs may
        take the provider out. A scan that starts with the breaker already armed
        scrapes nothing at all."""
        session = AsyncMock()
        session.get.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=refused_with
        )
        context = MagicMock()
        context.get.return_value = session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            await prime_account_limits()

        assert is_daily_quota_exhausted() is False
        assert ss_module._state.daily_quota_errors == 0

    @pytest.mark.asyncio
    async def test_priming_never_takes_the_provider_out(self):
        """ScreenScraper refuses a developer id it accepted a minute earlier while
        the scraping endpoints keep answering, so a scan whose scraping still works
        must not lose it to the account check."""
        response = MagicMock()
        response.text = AsyncMock(return_value=SS_LOGIN_ERROR_BODY)
        response.json = AsyncMock(return_value={})
        response.raise_for_status.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=http.HTTPStatus.FORBIDDEN,
        )
        session = AsyncMock()
        session.get.return_value = response
        context = MagicMock()
        context.get.return_value = session

        with patch("adapters.services.screenscraper.ctx_aiohttp_session", context):
            await prime_account_limits()

            assert ss_module._state.credentials_rejected is None

            # The next request is made rather than short-circuited, and it is the
            # one that arms the breaker.
            session.get.reset_mock()
            with pytest.raises(ScreenScraperCredentialsError):
                await ScreenScraperService()._request(
                    "https://api.screenscraper.fr/api2/jeuInfos.php"
                )

        session.get.assert_called_once()
        assert ss_module._state.credentials_rejected is SSCredentialSet.DEVELOPER


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

    def test_notes_the_unrecognized_rom_quota_without_warning(self, mock_log):
        """Running out of the submission allowance costs a contribution, not any
        metadata, so it is news rather than a problem."""
        ss_module._update_account_limits(
            _ssuser_response(maxrequestskoperday="2000", requestskotoday="1950")
        )

        assert mock_log.warning.call_count == 0
        messages = [_rendered(call) for call in mock_log.info.call_args_list]
        assert any("unrecognized" in message.lower() for message in messages)

    def test_the_submission_allowance_does_not_silence_the_scrape_warning(
        self, mock_log
    ):
        """The submission allowance is an order of magnitude smaller, so it runs
        out first; its notice must not consume the one-shot the scrape quota needs."""
        ss_module._update_account_limits(
            _ssuser_response(maxrequestskoperday="2000", requestskotoday="1950")
        )
        assert mock_log.warning.call_count == 0

        ss_module._update_account_limits(
            _ssuser_response(
                maxrequestsperday="20000",
                requeststoday="19500",
                maxrequestskoperday="2000",
                requestskotoday="1950",
            )
        )

        messages = [_rendered(call) for call in mock_log.warning.call_args_list]
        assert any("500" in message for message in messages)

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
