import asyncio
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from handler.redis_handler import async_cache
from handler.streaming import commands, session_store
from handler.streaming.config import ResolvedContainer, reset_cache, resolve_entry
from tasks.registry import SCHEDULED_TASKS
from tasks.scheduled.reap_streaming_sessions import (
    ReapStreamingSessionsTask,
    reap_streaming_sessions_task,
)

N64 = {
    "platform": "n64",
    "host": "http://192.168.1.10:3000",
    "broker_host": "http://192.168.1.10:8000",
}
PSX = {
    "platform": "psx",
    "host": "http://192.168.1.11:3000",
    "broker_host": "http://192.168.1.11:8000",
}


@pytest.fixture(autouse=True)
async def clear_streaming_sessions():
    await async_cache.flushall()


@contextmanager
def _streaming(*containers: dict, enabled: bool = True) -> Iterator[None]:
    cfg = MagicMock()
    cfg.STREAMING_ENABLED = enabled
    cfg.STREAMING_CONTAINERS = list(containers)
    reset_cache()
    with patch("handler.streaming.config.cm.get_config", return_value=cfg):
        try:
            yield
        finally:
            reset_cache()


def _resolved(entry: dict) -> ResolvedContainer:
    container = resolve_entry(entry)
    assert container is not None
    return container


def _ago(seconds: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


async def _hold(entry: dict, *, idle_seconds: int, **fields: Any) -> dict[str, Any]:
    """Store a claim on `entry` whose heartbeat is `idle_seconds` old."""
    session = {
        "user_id": 1,
        "platform": entry["platform"],
        "claimed_at": _ago(idle_seconds + 600),
        "last_seen": _ago(idle_seconds),
        **fields,
    }
    await async_cache.set(
        session_store.session_redis_key(_resolved(entry).key), json.dumps(session)
    )
    return session


async def _stored(entry: dict) -> dict[str, Any] | None:
    return await session_store.get_session(_resolved(entry).key)


STALE = session_store._STREAMING_SESSION_STALE_SECONDS + 60


def test_the_reaper_runs_every_minute():
    assert SCHEDULED_TASKS["reap_streaming_sessions"] is reap_streaming_sessions_task
    assert reap_streaming_sessions_task.enabled is True
    assert reap_streaming_sessions_task.cron_string == "* * * * *"


async def test_a_stale_session_goes_through_the_abandoned_teardown():
    with _streaming(N64):
        session = await _hold(N64, idle_seconds=STALE)
        with patch(
            "tasks.scheduled.reap_streaming_sessions.teardown_abandoned_session",
            new=AsyncMock(return_value=True),
        ) as teardown:
            await ReapStreamingSessionsTask().run()

    teardown.assert_awaited_once_with(_resolved(N64), _resolved(N64).key, session)


async def test_fresh_sessions_and_drain_markers_are_left_alone():
    with _streaming(N64, PSX):
        await _hold(N64, idle_seconds=10)
        await async_cache.set(
            session_store.session_redis_key(_resolved(PSX).key),
            session_store.drain_marker("draining"),
        )
        with patch(
            "tasks.scheduled.reap_streaming_sessions.teardown_abandoned_session",
            new=AsyncMock(return_value=True),
        ) as teardown:
            await ReapStreamingSessionsTask().run()

    teardown.assert_not_awaited()


async def test_a_shared_container_tears_down_under_the_sessions_own_platform():
    """Records sharing a key differ in emulator and card sync, so the session's
    saves have to go out under the platform it was claimed for."""
    shared = {
        "host": N64["host"],
        "broker_host": N64["broker_host"],
        "platforms": {"n64": "mupen64plus", "psx": "duckstation"},
    }
    with _streaming(shared):
        await _hold(N64, idle_seconds=STALE, platform="psx")
        with patch(
            "tasks.scheduled.reap_streaming_sessions.teardown_abandoned_session",
            new=AsyncMock(return_value=True),
        ) as teardown:
            await ReapStreamingSessionsTask().run()

    teardown.assert_awaited_once()
    (record, _, _), _ = teardown.call_args
    assert record.platform == "psx"


async def test_nothing_runs_while_streaming_is_disabled():
    with _streaming(N64, enabled=False):
        await _hold(N64, idle_seconds=STALE)
        with patch(
            "tasks.scheduled.reap_streaming_sessions.teardown_abandoned_session",
            new=AsyncMock(return_value=True),
        ) as teardown:
            await ReapStreamingSessionsTask().run()

    teardown.assert_not_awaited()


async def test_a_reaped_session_frees_its_container_and_leaves_a_notice():
    with _streaming(N64):
        session = await _hold(N64, idle_seconds=STALE)
        with (
            patch(
                "handler.streaming.lifecycle.quiesce_container",
                new=AsyncMock(return_value=commands.StopOutcome()),
            ) as quiesce,
            patch("handler.streaming.lifecycle.record_play_session") as played,
        ):
            await ReapStreamingSessionsTask().run()

    quiesce.assert_awaited_once()
    played.assert_awaited_once_with(session)
    assert await _stored(N64) is None
    notice = await session_store.get_termination(_resolved(N64).key, 1)
    assert notice is not None and notice["reason"] == "abandoned"


async def test_the_run_waits_for_the_exit_save_pull_it_spawned():
    """A worker's event loop stops with the job, so a pull still spawned when
    the run returns would never file the saves or clear its pending mark."""
    pulled = asyncio.Event()

    async def pull(*args: Any, **kwargs: Any) -> None:
        await asyncio.sleep(0.05)
        pulled.set()

    with _streaming(N64):
        await _hold(N64, idle_seconds=STALE, rom_id=7)
        with (
            patch(
                "handler.streaming.lifecycle.quiesce_container",
                new=AsyncMock(return_value=commands.StopOutcome()),
            ),
            patch("handler.streaming.lifecycle.record_play_session"),
            patch("handler.streaming.saves.pull_saves_to_library", new=pull),
        ):
            await ReapStreamingSessionsTask().run()

    assert pulled.is_set()


async def test_overlapping_runs_tear_a_session_down_once():
    """Two workers can both see the same stale session; the drain marker's
    compare-and-set lets only one of them stop the emulator."""
    stops = 0

    async def quiesce(*args: Any, **kwargs: Any) -> commands.StopOutcome:
        nonlocal stops
        stops += 1
        await asyncio.sleep(0.05)
        return commands.StopOutcome()

    # Both runs read the stale session before either marks it.
    both_read = asyncio.Barrier(2)

    async def read_together(key: str) -> dict[str, Any] | None:
        session = await session_store.get_session(key)
        await both_read.wait()
        return session

    with _streaming(N64):
        await _hold(N64, idle_seconds=STALE)
        with (
            patch(
                "tasks.scheduled.reap_streaming_sessions.get_session",
                new=read_together,
            ),
            patch("handler.streaming.lifecycle.quiesce_container", new=quiesce),
            patch("handler.streaming.lifecycle.record_play_session"),
        ):
            await asyncio.gather(
                ReapStreamingSessionsTask().run(), ReapStreamingSessionsTask().run()
            )

    assert stops == 1
    assert await _stored(N64) is None
