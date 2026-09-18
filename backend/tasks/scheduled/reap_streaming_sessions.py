import asyncio

from handler.streaming import background
from handler.streaming.config import (
    ResolvedContainer,
    container_for_session,
    containers_by_key,
    streaming_enabled,
)
from handler.streaming.lifecycle import teardown_abandoned_session
from handler.streaming.session_store import HOLD_CEILING_SECONDS, get_abandoned_session
from logger.logger import log
from tasks.tasks import PeriodicTask, TaskType


async def _reap(
    grouped: dict[str, list[ResolvedContainer]], container_key: str
) -> None:
    session = await get_abandoned_session(container_key)
    if session is None:
        return
    record = container_for_session(grouped, container_key, session.get("platform"))
    if record is None:
        return
    if await teardown_abandoned_session(
        record, container_key, session, claimed_by=None
    ):
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
            # RQ kills a job at its timeout, and a teardown cut short mid-evacuation
            # loses the card, so give it as long as the work may keep a hold.
            timeout=HOLD_CEILING_SECONDS,
            result_ttl=0,
        )

    async def run(self) -> None:
        if not self.enabled or not streaming_enabled():
            return

        # Concurrent, so one sick broker cannot hold up every other container.
        grouped = containers_by_key()
        results = await asyncio.gather(
            *(_reap(grouped, key) for key in grouped), return_exceptions=True
        )
        for key, result in zip(grouped, results, strict=True):
            if isinstance(result, Exception):
                log.error("streaming session reap failed, key=%s", key, exc_info=result)
        # The worker's event loop stops with this job, which would strand the
        # exit save pulls the teardowns spawned.
        await background.wait_for_sync_tasks()


reap_streaming_sessions_task = ReapStreamingSessionsTask()
