from unittest.mock import AsyncMock, MagicMock, patch

from handler.metadata.playmatch_handler import PlaymatchHandler
from utils import get_version


@patch("handler.metadata.playmatch_handler.ctx_httpx_client")
async def test_heartbeat_requests_health_without_query(mock_ctx_httpx_client):
    handler = PlaymatchHandler()
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "ok"}
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
