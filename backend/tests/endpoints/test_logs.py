import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status

from endpoints.logs import MAX_LOG_LIMIT
from endpoints.sockets.logs import get_recent_logs
from utils import json_module

SAMPLE_ENTRY = {"ts": 1, "level": "INFO", "module": "startup", "message": "hello"}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_get_logs_requires_auth(client):
    response = client.get("/api/logs")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_get_logs_forbidden_without_logs_read(client, viewer_access_token):
    # Viewers lack the `logs.read` (admin-only) scope the endpoint requires.
    response = client.get("/api/logs", headers=_auth(viewer_access_token))
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_get_logs_returns_entries_for_admin(client, access_token):
    with patch(
        "endpoints.logs.get_recent_logs",
        new_callable=AsyncMock,
        return_value=[SAMPLE_ENTRY],
    ):
        response = client.get("/api/logs", headers=_auth(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [SAMPLE_ENTRY]


def test_get_logs_disabled_returns_not_found(client, access_token):
    # When DISABLE_LOGS_VIEWER is set, the endpoint is gone even for admins.
    with patch("endpoints.logs.DISABLE_LOGS_VIEWER", True):
        response = client.get("/api/logs", headers=_auth(access_token))
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_logs_clamps_limit(client, access_token):
    with patch(
        "endpoints.logs.get_recent_logs",
        new_callable=AsyncMock,
        return_value=[],
    ) as mock_recent:
        # Above the cap → clamped down to MAX_LOG_LIMIT.
        client.get(
            f"/api/logs?limit={MAX_LOG_LIMIT + 5000}", headers=_auth(access_token)
        )
        mock_recent.assert_awaited_with(MAX_LOG_LIMIT)

        # Below 1 → clamped up to 1.
        mock_recent.reset_mock()
        client.get("/api/logs?limit=0", headers=_auth(access_token))
        mock_recent.assert_awaited_with(1)

        # In range → passed through unchanged.
        mock_recent.reset_mock()
        client.get("/api/logs?limit=25", headers=_auth(access_token))
        mock_recent.assert_awaited_with(25)


def test_get_recent_logs_returns_oldest_first_and_skips_malformed():
    # The ring buffer is newest-first (LPUSH); get_recent_logs must return
    # oldest-first and drop any unparseable entry.
    newest_first = [
        json_module.dumps({"ts": 3, "level": "INFO", "module": "m", "message": "c"}),
        "not-json",
        json_module.dumps({"ts": 2, "level": "INFO", "module": "m", "message": "b"}),
        json_module.dumps({"ts": 1, "level": "INFO", "module": "m", "message": "a"}),
    ]
    mock_cache = MagicMock()
    mock_cache.lrange = AsyncMock(return_value=newest_first)

    with patch("endpoints.sockets.logs.async_cache", mock_cache):
        result = asyncio.run(get_recent_logs(10))

    assert [entry["ts"] for entry in result] == [1, 2, 3]
