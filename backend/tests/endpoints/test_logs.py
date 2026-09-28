import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status

from endpoints.logs import MAX_LOG_LIMIT
from endpoints.sockets.logs import (
    FORWARDER_LOCK_KEY,
    get_recent_logs,
    start_log_forwarder,
)
from utils import json_module

SAMPLE_ENTRY = {"ts": 1, "level": "INFO", "module": "startup", "message": "hello"}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_get_logs_requires_auth(client):
    response = client.get("/api/logs")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


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


def _fake_lock_cache() -> MagicMock:
    """A str-valued lock store, since the test fakeredis returns bytes."""
    store: dict[str, Any] = {}

    async def set_(key, value, nx=False, ex=None):
        if nx and key in store:
            return None
        store[key] = value
        return True

    async def get(key):
        return store.get(key)

    async def delete(key):
        store.pop(key, None)

    cache = MagicMock()
    cache.store = store
    cache.set = AsyncMock(side_effect=set_)
    cache.get = AsyncMock(side_effect=get)
    cache.delete = AsyncMock(side_effect=delete)
    return cache


def test_log_forwarder_resumes_after_a_redis_error():
    broken = MagicMock()
    broken.subscribe = AsyncMock(side_effect=ConnectionError("valkey restarted"))
    broken.aclose = AsyncMock()

    healthy = MagicMock()
    healthy.subscribe = AsyncMock()
    healthy.aclose = AsyncMock()
    messages = [{"data": json_module.dumps(SAMPLE_ENTRY)}]

    async def get_message(**kwargs):
        if messages:
            return messages.pop()
        await asyncio.sleep(kwargs["timeout"])
        return None

    healthy.get_message = AsyncMock(side_effect=get_message)

    cache = _fake_lock_cache()
    cache.pubsub = MagicMock(side_effect=[broken, healthy])
    manager = MagicMock()

    async def run() -> None:
        forwarded = asyncio.Event()
        manager.emit = AsyncMock(side_effect=lambda *a, **kw: forwarded.set())
        task = asyncio.create_task(start_log_forwarder())
        await asyncio.wait_for(forwarded.wait(), timeout=5)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    with (
        patch("endpoints.sockets.logs.DISABLE_LOGS_VIEWER", False),
        patch("endpoints.sockets.logs.FORWARDER_LOCK_TTL", 0.03),
        patch("endpoints.sockets.logs.async_cache", cache),
        patch(
            "endpoints.sockets.logs.socket_handler.write_manager",
            return_value=manager,
        ),
    ):
        asyncio.run(run())

    manager.emit.assert_any_await("logs:entry", SAMPLE_ENTRY, room="admin")
    # The dead connection is closed even though it never subscribed.
    broken.aclose.assert_awaited_once()
    healthy.aclose.assert_awaited_once()
    # Cancelling releases the lock so a restart picks up straight away.
    assert FORWARDER_LOCK_KEY not in cache.store
