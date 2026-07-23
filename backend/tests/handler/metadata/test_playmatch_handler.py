import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from handler.metadata.playmatch_handler import PlaymatchHandler
from utils import get_version


@patch("handler.metadata.playmatch_handler.ctx_httpx_client")
async def test_heartbeat_accepts_plain_text_health_response(mock_ctx_httpx_client):
    # /health returns a 200 with the plain-text body "Healthy", not JSON.
    handler = PlaymatchHandler()
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.text = "Healthy"
    mock_response.json.side_effect = json.JSONDecodeError(
        "Expecting value", "Healthy", 0
    )
    mock_client.get.return_value = mock_response
    mock_ctx_httpx_client.get.return_value = mock_client

    with (
        patch.object(handler, "is_enabled", return_value=True),
        patch(
            "handler.metadata.playmatch_handler._rate_limiter.acquire",
            new_callable=AsyncMock,
        ),
    ):
        assert await handler.heartbeat() is True

    mock_client.get.assert_awaited_once_with(
        handler.healthcheck_url,
        headers={"user-agent": f"RomM/{get_version()}"},
        timeout=60,
    )
    mock_response.raise_for_status.assert_called_once()


@patch("handler.metadata.playmatch_handler.ctx_httpx_client")
async def test_heartbeat_returns_false_on_http_error(mock_ctx_httpx_client):
    handler = PlaymatchHandler()
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Service Unavailable", request=MagicMock(), response=MagicMock()
    )
    mock_client.get.return_value = mock_response
    mock_ctx_httpx_client.get.return_value = mock_client

    with (
        patch.object(handler, "is_enabled", return_value=True),
        patch(
            "handler.metadata.playmatch_handler._rate_limiter.acquire",
            new_callable=AsyncMock,
        ),
    ):
        assert await handler.heartbeat() is False


async def test_heartbeat_returns_false_when_disabled():
    handler = PlaymatchHandler()
    with patch.object(handler, "is_enabled", return_value=False):
        assert await handler.heartbeat() is False
