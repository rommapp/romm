import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestServer
from fastapi import HTTPException

import config
from adapters.services import igdb
from adapters.services.igdb import IGDBService
from utils.context import ctx_aiohttp_session


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


Reply = tuple[int, Any] | float


class FakeIGDB:
    """A local IGDB that plays back scripted replies per endpoint."""

    def __init__(self) -> None:
        self.replies: dict[str, list[Reply]] = {}
        self.requests: list[tuple[str, str, dict[str, str]]] = []

    async def handle(self, request: web.Request) -> web.Response:
        endpoint = request.match_info["endpoint"]
        self.requests.append((endpoint, await request.text(), dict(request.headers)))
        reply = self.replies[endpoint].pop(0)
        if isinstance(reply, float):
            await asyncio.sleep(reply)
            return web.json_response([])
        status, body = reply
        if isinstance(body, bytes):
            return web.Response(status=status, body=body)
        return web.json_response(body, status=status)


class FakeTwitchAuth:
    def __init__(self, token: str = "tok") -> None:
        self.token = token
        self.refreshes = 0

    async def get_oauth_token(self) -> str:
        return self.token

    async def _update_twitch_token(self) -> str:
        self.refreshes += 1
        return self.token


@pytest_asyncio.fixture
async def igdb_server() -> AsyncIterator[tuple[FakeIGDB, str]]:
    fake = FakeIGDB()
    app = web.Application()
    app.router.add_post("/v4/{endpoint}", fake.handle)
    server = TestServer(app)
    await server.start_server()
    session = aiohttp.ClientSession()
    token = ctx_aiohttp_session.set(session)
    try:
        yield fake, str(server.make_url("/v4"))
    finally:
        ctx_aiohttp_session.reset(token)
        await session.close()
        await server.close()


@pytest.fixture
def no_backoff(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    sleep = AsyncMock()
    # Swap only igdb's reference, so the test server and aiohttp still sleep.
    monkeypatch.setattr(
        "adapters.services.igdb.asyncio", MagicMock(wraps=asyncio, sleep=sleep)
    )
    return sleep


GAME = {"id": 1, "name": "Pokemon Red"}


class TestIGDBServiceAgainstAServer:
    async def test_sends_an_apicalypse_query_with_credentials(
        self, igdb_server: tuple[FakeIGDB, str]
    ):
        fake, url = igdb_server
        fake.replies["games"] = [(200, [GAME])]
        service = IGDBService(twitch_auth=FakeTwitchAuth(), base_url=url)  # type: ignore[arg-type]

        games = await service.list_games(
            search_term="Pokémon Red",
            fields=["id", "name"],
            where="platforms=4",
            limit=5,
        )

        assert games == [GAME]
        [(endpoint, body, headers)] = fake.requests
        assert endpoint == "games"
        assert (
            body == 'search "Pokemon Red"; fields id,name; where platforms=4; limit 5;'
        )
        assert headers["Authorization"] == "Bearer tok"
        assert headers["Client-ID"] == config.IGDB_CLIENT_ID
        assert headers["User-Agent"].startswith("RomM/")

    async def test_search_uses_the_search_endpoint(
        self, igdb_server: tuple[FakeIGDB, str]
    ):
        fake, url = igdb_server
        fake.replies["search"] = [(200, [{"id": 9, "game": {"id": 1}}])]
        service = IGDBService(twitch_auth=FakeTwitchAuth(), base_url=url)  # type: ignore[arg-type]

        results = await service.search(fields=["game.id"], where='name ~ *"Red"*')

        assert results == [{"id": 9, "game": {"id": 1}}]
        assert fake.requests[0][0] == "search"

    async def test_an_expired_token_is_refreshed_and_retried(
        self, igdb_server: tuple[FakeIGDB, str]
    ):
        fake, url = igdb_server
        fake.replies["games"] = [(401, {}), (200, [GAME])]
        auth = FakeTwitchAuth()
        service = IGDBService(twitch_auth=auth, base_url=url)  # type: ignore[arg-type]

        assert await service.list_games(fields=["id"]) == [GAME]
        assert auth.refreshes == 1
        assert len(fake.requests) == 2

    async def test_a_second_unauthorized_reply_gives_up(
        self, igdb_server: tuple[FakeIGDB, str]
    ):
        fake, url = igdb_server
        fake.replies["games"] = [(401, {}), (401, {})]
        service = IGDBService(twitch_auth=FakeTwitchAuth(), base_url=url)  # type: ignore[arg-type]

        assert await service.list_games(fields=["id"]) == []

    async def test_a_rate_limited_request_backs_off_and_retries(
        self, igdb_server: tuple[FakeIGDB, str], no_backoff: AsyncMock
    ):
        fake, url = igdb_server
        fake.replies["games"] = [(429, {}), (200, [GAME])]
        service = IGDBService(twitch_auth=FakeTwitchAuth(), base_url=url)  # type: ignore[arg-type]

        assert await service.list_games(fields=["id"]) == [GAME]
        no_backoff.assert_awaited_once_with(2)

    async def test_a_server_error_is_no_result_without_a_retry(
        self, igdb_server: tuple[FakeIGDB, str]
    ):
        fake, url = igdb_server
        fake.replies["games"] = [(500, {})]
        service = IGDBService(twitch_auth=FakeTwitchAuth(), base_url=url)  # type: ignore[arg-type]

        assert await service.list_games(fields=["id"]) == []
        assert len(fake.requests) == 1

    async def test_a_reply_that_is_not_json_is_no_result(
        self, igdb_server: tuple[FakeIGDB, str]
    ):
        fake, url = igdb_server
        fake.replies["games"] = [(200, b"<html>maintenance</html>")]
        service = IGDBService(twitch_auth=FakeTwitchAuth(), base_url=url)  # type: ignore[arg-type]

        assert await service.list_games(fields=["id"]) == []

    async def test_a_timed_out_request_is_retried_once(
        self, igdb_server: tuple[FakeIGDB, str], monkeypatch: pytest.MonkeyPatch
    ):
        fake, url = igdb_server
        fake.replies["games"] = [1.0, (200, [GAME])]
        service = IGDBService(twitch_auth=FakeTwitchAuth(), base_url=url)  # type: ignore[arg-type]

        result = await service._request(
            f"{url}/games", list[dict[str, Any]], fields=["id"], request_timeout=0.2  # type: ignore[arg-type]
        )

        assert result == [GAME]

    async def test_two_timeouts_are_no_result(self, igdb_server: tuple[FakeIGDB, str]):
        fake, url = igdb_server
        fake.replies["games"] = [1.0, 1.0]
        service = IGDBService(twitch_auth=FakeTwitchAuth(), base_url=url)  # type: ignore[arg-type]

        result = await service._request(
            f"{url}/games", list[dict[str, Any]], fields=["id"], request_timeout=0.2  # type: ignore[arg-type]
        )

        assert result is None

    async def test_missing_credentials_are_unavailable(
        self, igdb_server: tuple[FakeIGDB, str]
    ):
        fake, url = igdb_server
        service = IGDBService(twitch_auth=FakeTwitchAuth(token=""), base_url=url)  # type: ignore[arg-type]

        with pytest.raises(HTTPException) as exc:
            await service.list_games(fields=["id"])

        assert exc.value.status_code == 503
        assert exc.value.detail == "Invalid IGDB credentials"
        assert fake.requests == []

    async def test_an_unreachable_igdb_is_unavailable(
        self, igdb_server: tuple[FakeIGDB, str]
    ):
        service = IGDBService(
            twitch_auth=FakeTwitchAuth(),  # type: ignore[arg-type]
            base_url="http://127.0.0.1:9/v4",
        )

        with pytest.raises(HTTPException) as exc:
            await service.list_games(fields=["id"])

        assert exc.value.status_code == 503
