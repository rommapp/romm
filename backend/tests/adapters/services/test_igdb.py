import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException, status
from tests.adapters.services.scripted_server import (
    DISCONNECT,
    ScriptedServer,
    scripted_server,
)

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
        mock_response.read = AsyncMock(return_value=json.dumps([{"id": 1}]).encode())
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
            result = await service._request("https://api.igdb.com/v4/games", object)

        assert result == [{"id": 1}]
        # The rate-limiter slot must be reserved, and before the request is sent.
        acquire_mock.assert_awaited_once()
        mock_session.post.assert_awaited_once()
        assert call_order == [
            "acquire",
            "post",
        ], "rate limiter must be acquired before the POST is sent"


@pytest_asyncio.fixture
async def igdb_server(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[ScriptedServer, IGDBService, MagicMock]]:
    monkeypatch.setattr(igdb, "IGDB_CLIENT_ID", "client")
    twitch_auth = MagicMock(
        get_oauth_token=AsyncMock(return_value="token"),
        _update_twitch_token=AsyncMock(),
    )
    async with scripted_server("/v4") as (fake, url):
        yield fake, IGDBService(twitch_auth=twitch_auth, base_url=url), twitch_auth


@pytest.fixture
def no_backoff(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    sleep = AsyncMock()
    # Swap only this module's reference, so the test server and aiohttp still sleep.
    monkeypatch.setattr(
        "adapters.services.provider_http.asyncio", MagicMock(wraps=asyncio, sleep=sleep)
    )
    return sleep


GAMES = [{"id": 1}]


class TestAgainstAServer:
    async def _games(self, service: IGDBService) -> Any:
        return await service._request(
            f"{service.url}/games", list[dict[str, Any]], request_timeout=0.2
        )

    async def test_a_timed_out_request_is_retried_once(
        self, igdb_server: tuple[ScriptedServer, IGDBService, MagicMock]
    ):
        fake, service, _ = igdb_server
        fake.replies["games"] = [5.0, (200, GAMES)]

        assert await self._games(service) == GAMES
        assert len(fake.requests) == 2

    async def test_two_timeouts_are_no_result(
        self, igdb_server: tuple[ScriptedServer, IGDBService, MagicMock]
    ):
        fake, service, _ = igdb_server
        fake.replies["games"] = [5.0, 5.0]

        assert await self._games(service) is None

    async def test_a_rejected_token_is_refreshed_and_retried(
        self, igdb_server: tuple[ScriptedServer, IGDBService, MagicMock]
    ):
        fake, service, twitch_auth = igdb_server
        fake.replies["games"] = [(401, {}), (200, GAMES)]

        assert await self._games(service) == GAMES
        twitch_auth._update_twitch_token.assert_awaited_once()
        assert fake.requests[-1].headers["Authorization"] == "Bearer token"

    async def test_a_rate_limited_request_backs_off_and_retries(
        self,
        igdb_server: tuple[ScriptedServer, IGDBService, MagicMock],
        no_backoff: AsyncMock,
    ):
        fake, service, _ = igdb_server
        fake.replies["games"] = [(429, {}), (200, GAMES)]

        assert await self._games(service) == GAMES
        no_backoff.assert_awaited_once_with(2)

    @pytest.mark.parametrize("first", [5.0, (429, {})], ids=["timeout", "rate_limited"])
    async def test_a_dropped_retry_is_unavailable(
        self,
        igdb_server: tuple[ScriptedServer, IGDBService, MagicMock],
        no_backoff: AsyncMock,
        first: Any,
    ):
        fake, service, _ = igdb_server
        # aiohttp resends only idempotent requests on a dropped connection, not a POST.
        fake.replies["games"] = [first, DISCONNECT]

        with pytest.raises(HTTPException) as exc:
            await self._games(service)

        assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


class TestRequestsAgainstAServer:
    async def test_sends_an_apicalypse_query_with_credentials(
        self, igdb_server: tuple[ScriptedServer, IGDBService, MagicMock]
    ):
        fake, service, _ = igdb_server
        fake.replies["games"] = [(200, GAMES)]

        games = await service.list_games(
            search_term="Pokémon Red",
            fields=["id", "name"],
            where="platforms=4",
            limit=5,
        )

        assert games == GAMES
        [request] = fake.endpoint("games")
        assert (
            await request.text()
            == 'search "Pokemon Red"; fields id,name; where platforms=4; limit 5;'
        )
        assert request.headers["Authorization"] == "Bearer token"
        assert request.headers["Client-ID"] == "client"
        assert request.headers["User-Agent"].startswith("RomM/")

    async def test_search_uses_the_search_endpoint(
        self, igdb_server: tuple[ScriptedServer, IGDBService, MagicMock]
    ):
        fake, service, _ = igdb_server
        fake.replies["search"] = [(200, [{"id": 9, "game": {"id": 1}}])]

        results = await service.search(fields=["game.id"], where='name ~ *"Red"*')

        assert results == [{"id": 9, "game": {"id": 1}}]
        assert len(fake.endpoint("search")) == 1

    async def test_a_second_unauthorized_reply_gives_up(
        self, igdb_server: tuple[ScriptedServer, IGDBService, MagicMock]
    ):
        fake, service, _ = igdb_server
        fake.replies["games"] = [(401, {}), (401, {})]

        assert await service.list_games(fields=["id"]) == []
        assert len(fake.requests) == 2

    async def test_a_server_error_is_no_result_without_a_retry(
        self, igdb_server: tuple[ScriptedServer, IGDBService, MagicMock]
    ):
        fake, service, _ = igdb_server
        fake.replies["games"] = [(500, {})]

        assert await service.list_games(fields=["id"]) == []
        assert len(fake.requests) == 1

    async def test_a_reply_that_is_not_json_is_no_result(
        self, igdb_server: tuple[ScriptedServer, IGDBService, MagicMock]
    ):
        fake, service, _ = igdb_server
        fake.replies["games"] = [(200, b"<html>maintenance</html>")]

        assert await service.list_games(fields=["id"]) == []

    async def test_missing_credentials_are_unavailable(
        self, igdb_server: tuple[ScriptedServer, IGDBService, MagicMock]
    ):
        fake, service, twitch_auth = igdb_server
        twitch_auth.get_oauth_token.return_value = ""

        with pytest.raises(HTTPException) as exc:
            await service.list_games(fields=["id"])

        assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert exc.value.detail == "Invalid IGDB credentials"
        assert fake.requests == []

    async def test_an_unreachable_igdb_is_unavailable(
        self, igdb_server: tuple[ScriptedServer, IGDBService, MagicMock]
    ):
        _, _, twitch_auth = igdb_server
        service = IGDBService(twitch_auth=twitch_auth, base_url="http://127.0.0.1:9/v4")

        with pytest.raises(HTTPException) as exc:
            await service.list_games(fields=["id"])

        assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
