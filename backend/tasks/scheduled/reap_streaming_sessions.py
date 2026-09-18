import asyncio

from handler.streaming import background
from handler.streaming.config import (
    ResolvedContainer,
    container_for_session,
    containers_by_key,
    streaming_enabled,
)
from handler.streaming.lifecycle import teardown_abandoned_session
from handler.streaming.session_store import get_session, session_is_stale
from logger.logger import log
from tasks.tasks import PeriodicTask, TaskType


async def _reap(container_key: str, entries: list[ResolvedContainer]) -> None:
    session = await get_session(container_key)
    if session is None or session.get("draining") or not session_is_stale(session):
        return
    record = container_for_session(
        {container_key: entries}, container_key, session.get("platform")
    )
    if record is None:
        return
    if await teardown_abandoned_session(record, container_key, session):
        log.info(
            "reaped abandoned streaming session, platform=%s user_id=%s",
            record.platform,
            session.get("user_id"),
        )


class ReapStreamingSessionsTask(PeriodicTask):
    def __init__(self):
        super().__init__(
            title="Scheduled streaming session reaper",
            description="Stops streaming sessions whose player stopped sending heartbeats",
            task_type=TaskType.CLEANUP,
            enabled=True,
            manual_run=False,
            cron_string="* * * * *",  # Every minute
        )

    async def run(self) -> None:
        if not self.enabled or not streaming_enabled():
            return

        # Concurrent, so one sick broker cannot hold up every other container.
        await asyncio.gather(
            *(_reap(key, entries) for key, entries in containers_by_key().items())
        )
        # The worker's event loop stops with this job, which would strand the
        # exit save pulls the teardowns spawned.
        await background.wait_for_sync_tasks()


reap_streaming_sessions_task = ReapStreamingSessionsTask()
