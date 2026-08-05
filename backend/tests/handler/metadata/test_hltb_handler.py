from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException, status

from handler.metadata.hltb_handler import HLTBHandler
from utils import get_version


def _handler() -> HLTBHandler:
    handler = HLTBHandler()
    handler.security_token = "token-1"
    handler.hp_key = "ign_aaaa"
    handler.hp_val = "val-1"
    return handler


def _response(status_code: int = 200, json_body: dict | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=response
        )
    else:
        response.json.return_value = json_body or {}
    return response


@pytest.fixture(autouse=True)
def acquire():
    with (
        patch(
            "handler.metadata.hltb_handler._rate_limiter.acquire",
            new_callable=AsyncMock,
        ) as mock_acquire,
        patch("handler.metadata.hltb_handler.asyncio.sleep", new_callable=AsyncMock),
    ):
        yield mock_acquire


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_request_renews_session_and_retries_on_403(mock_ctx_httpx_client):
    handler = _handler()
    mock_client = AsyncMock()
    mock_client.post.side_effect = [
        _response(status.HTTP_403_FORBIDDEN),
        _response(json_body={"data": [{"game_id": 1}]}),
    ]
    # The renewal goes through /init and hands back a fresh session.
    mock_client.get.return_value = _response(
        json_body={"token": "token-2", "hpKey": "ign_bbbb", "hpVal": "val-2"}
    )
    mock_ctx_httpx_client.get.return_value = mock_client

    result = await handler._request("https://howlongtobeat.com/api/bleed", {"a": 1})

    assert result == {"data": [{"game_id": 1}]}
    assert mock_client.post.await_count == 2
    mock_client.get.assert_awaited_once()

    # The retry must carry the renewed session, not the rejected one.
    retry_kwargs = mock_client.post.await_args_list[1].kwargs
    assert retry_kwargs["headers"]["x-auth-token"] == "token-2"
    assert retry_kwargs["headers"]["x-hp-key"] == "ign_bbbb"
    assert retry_kwargs["headers"]["x-hp-val"] == "val-2"
    # The rotated honeypot key replaces the old one rather than joining it.
    assert retry_kwargs["json"] == {"a": 1, "ign_bbbb": "val-2"}


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_request_does_not_mutate_caller_payload(mock_ctx_httpx_client):
    handler = _handler()
    mock_client = AsyncMock()
    mock_client.post.return_value = _response(json_body={"data": []})
    mock_ctx_httpx_client.get.return_value = mock_client

    payload = {"a": 1}
    await handler._request("https://howlongtobeat.com/api/bleed", payload)

    assert payload == {"a": 1}


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_request_uses_session_renewed_while_it_was_paced(
    mock_ctx_httpx_client, acquire
):
    # The handler is a shared singleton, so a peer scanning another ROM can renew
    # the session while this call is waiting on the rate limiter.
    handler = _handler()
    mock_client = AsyncMock()
    mock_client.post.return_value = _response(json_body={"data": []})
    mock_ctx_httpx_client.get.return_value = mock_client

    async def renew_while_waiting() -> None:
        handler.security_token = "token-from-peer"
        handler.hp_key = "ign_peer"
        handler.hp_val = "val-peer"

    acquire.side_effect = renew_while_waiting

    await handler._request("https://howlongtobeat.com/api/bleed", {"a": 1})

    kwargs = mock_client.post.await_args.kwargs
    assert kwargs["headers"]["x-auth-token"] == "token-from-peer"
    assert kwargs["json"] == {"a": 1, "ign_peer": "val-peer"}


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_request_bails_if_session_is_lost_while_it_was_paced(
    mock_ctx_httpx_client, acquire
):
    handler = _handler()
    mock_client = AsyncMock()
    mock_ctx_httpx_client.get.return_value = mock_client

    async def lose_session_while_waiting() -> None:
        handler.security_token = None

    acquire.side_effect = lose_session_while_waiting

    assert await handler._request("https://howlongtobeat.com/api/bleed", {}) == {}
    mock_client.post.assert_not_awaited()


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_session_renewal_is_rate_limited_too(mock_ctx_httpx_client, acquire):
    handler = _handler()
    mock_client = AsyncMock()
    mock_client.post.side_effect = [
        _response(status.HTTP_403_FORBIDDEN),
        _response(json_body={"data": []}),
    ]
    mock_client.get.return_value = _response(
        json_body={"token": "token-2", "hpKey": "ign_bbbb", "hpVal": "val-2"}
    )
    mock_ctx_httpx_client.get.return_value = mock_client

    await handler._request("https://howlongtobeat.com/api/bleed", {})

    # Two POSTs plus the /init renewal in between, all paced.
    assert acquire.await_count == 3


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_github_endpoint_fetch_is_not_rate_limited(
    mock_ctx_httpx_client, acquire
):
    # The endpoint fixture lives on GitHub, so it should not spend HLTB budget.
    handler = HLTBHandler()
    mock_client = AsyncMock()
    mock_client.get.return_value = _response_with_text(
        "https://howlongtobeat.com/api/rotated"
    )
    mock_ctx_httpx_client.get.return_value = mock_client

    await handler._fetch_search_endpoint()

    acquire.assert_not_awaited()


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_debug_log_does_not_leak_session_material(mock_ctx_httpx_client):
    # Logs are downloadable via /api/logs and routinely pasted into bug reports,
    # and the token decodes to a string containing the host's public IP.
    handler = _handler()
    mock_client = AsyncMock()
    mock_client.post.return_value = _response(json_body={"data": []})
    mock_ctx_httpx_client.get.return_value = mock_client

    with patch("handler.metadata.hltb_handler.log.debug") as mock_debug:
        await handler._request(
            "https://howlongtobeat.com/api/bleed", {"searchTerms": ["Chrono"]}
        )

    logged = repr(mock_debug.call_args.args)
    for secret in ("token-1", "ign_aaaa", "val-1"):
        assert secret not in logged

    # The parts that make the log useful are still there.
    assert "Chrono" in logged
    assert "[redacted]" in logged


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_request_backs_off_and_retries_on_429(mock_ctx_httpx_client):
    handler = _handler()
    mock_client = AsyncMock()
    mock_client.post.side_effect = [
        _response(status.HTTP_429_TOO_MANY_REQUESTS),
        _response(json_body={"data": []}),
    ]
    mock_ctx_httpx_client.get.return_value = mock_client

    assert await handler._request("https://howlongtobeat.com/api/bleed", {}) == {
        "data": []
    }
    assert mock_client.post.await_count == 2
    # A rate limit is not a session problem, so no renewal should be attempted.
    mock_client.get.assert_not_awaited()


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_request_gives_up_when_session_renewal_fails(mock_ctx_httpx_client):
    handler = _handler()
    mock_client = AsyncMock()
    mock_client.post.return_value = _response(status.HTTP_403_FORBIDDEN)
    mock_client.get.return_value = _response(json_body={})
    mock_ctx_httpx_client.get.return_value = mock_client

    assert await handler._request("https://howlongtobeat.com/api/bleed", {}) == {}
    assert mock_client.post.await_count == 1


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_persistent_403_reports_session_cause_not_connectivity(
    mock_ctx_httpx_client,
):
    handler = _handler()
    mock_client = AsyncMock()
    mock_client.post.return_value = _response(status.HTTP_403_FORBIDDEN)
    mock_client.get.return_value = _response(
        json_body={"token": "token-2", "hpKey": "ign_bbbb", "hpVal": "val-2"}
    )
    mock_ctx_httpx_client.get.return_value = mock_client

    with pytest.raises(HTTPException) as exc_info:
        await handler._request("https://howlongtobeat.com/api/bleed", {})

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "internet connection" not in exc_info.value.detail
    assert "rejected the session" in exc_info.value.detail
    assert mock_client.post.await_count == 3


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_rotated_endpoint_reports_404_cause(mock_ctx_httpx_client):
    handler = _handler()
    mock_client = AsyncMock()
    mock_client.post.return_value = _response(status.HTTP_404_NOT_FOUND)
    mock_ctx_httpx_client.get.return_value = mock_client

    with pytest.raises(HTTPException) as exc_info:
        await handler._request("https://howlongtobeat.com/api/find", {})

    assert "rotated" in exc_info.value.detail
    # A 404 is not retryable, so it should fail on the first attempt.
    assert mock_client.post.await_count == 1


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_connect_error_still_reports_connectivity(mock_ctx_httpx_client):
    handler = _handler()
    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.ConnectError("no route")
    mock_ctx_httpx_client.get.return_value = mock_client

    with pytest.raises(HTTPException) as exc_info:
        await handler._request("https://howlongtobeat.com/api/bleed", {})

    assert "internet connection" in exc_info.value.detail


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_request_returns_empty_without_a_session(mock_ctx_httpx_client):
    handler = HLTBHandler()
    mock_client = AsyncMock()
    mock_ctx_httpx_client.get.return_value = mock_client

    assert await handler._request("https://howlongtobeat.com/api/bleed", {}) == {}
    mock_client.post.assert_not_awaited()


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_initialize_fetches_endpoint_then_session(mock_ctx_httpx_client):
    handler = HLTBHandler()
    mock_client = AsyncMock()
    mock_client.get.side_effect = [
        _response_with_text("https://howlongtobeat.com/api/rotated"),
        _response(json_body={"token": "t", "hpKey": "k", "hpVal": "v"}),
    ]
    mock_ctx_httpx_client.get.return_value = mock_client

    await handler.initialize()

    assert handler.search_url == "https://howlongtobeat.com/api/rotated"
    assert handler.search_init_url == "https://howlongtobeat.com/api/rotated/init"
    assert handler._has_session()
    # The session must be requested from the rotated endpoint, not the stale default.
    assert (
        mock_client.get.await_args_list[1].args[0]
        == "https://howlongtobeat.com/api/rotated/init"
    )


def _response_with_text(text: str) -> MagicMock:
    response = _response()
    response.text = text
    return response


@patch("handler.metadata.hltb_handler.HLTB_API_ENABLED", True)
@patch("handler.metadata.hltb_handler.ctx_httpx_client")
async def test_heartbeat_sends_the_user_agent_hltb_requires(mock_ctx_httpx_client):
    handler = HLTBHandler()
    mock_client = AsyncMock()
    mock_client.get.return_value = _response()
    mock_ctx_httpx_client.get.return_value = mock_client

    with patch.object(handler, "is_enabled", return_value=True):
        assert await handler.heartbeat() is True

    # HLTB rejects requests without a recognised user agent.
    headers = mock_client.get.await_args.kwargs["headers"]
    assert headers["User-Agent"] == f"RomM/{get_version()}"
    assert headers["Referer"] == "https://howlongtobeat.com"
