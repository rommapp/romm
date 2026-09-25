import asyncio

from handler.redis_handler import STREAMING_QUEUE_NAME
from handler.streaming.config import (
    ResolvedContainer,
    container_for_session,
    containers_by_key,
    streaming_enabled,
)
from handler.streaming.lifecycle import teardown_abandoned_session
from handler.streaming.saves import SAVE_PULL_TTL_SECONDS
from handler.streaming.session_store import (
    HOLD_CEILING_SECONDS,
    get_abandoned_session,
    in_restart_grace,
)
from logger.logger import log
from tasks.tasks import PeriodicTask, TaskType


async def _reap(
    grouped: dict[str, list[ResolvedContainer]], container_key: str
) -> None:
    try:
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
    except Exception:
        log.exception("streaming session reap failed, key=%s", container_key)


class ReapStreamingSessionsTask(PeriodicTask):
    def __init__(self):
        super().__init__(
            title="Scheduled streaming session reaper",
            description="Stops streaming sessions whose player stopped sending heartbeats",
            task_type=TaskType.CLEANUP,
            # Read once, as cron registers only enabled tasks when it starts.
            enabled=streaming_enabled(),
            manual_run=False,
            cron_string="* * * * *",  # Every minute
            # RQ kills a job at its timeout, so it has to cover a teardown holding
            # its marker to the ceiling plus the exit save pull it then waits out.
            timeout=HOLD_CEILING_SECONDS + SAVE_PULL_TTL_SECONDS,
            result_ttl=0,
            queue_name=STREAMING_QUEUE_NAME,
        )

    async def run(self) -> None:
        if not self.enabled or await in_restart_grace():
            return

        # Empty once streaming is disabled, so a disabled install reaps nothing.
        grouped = containers_by_key()
        # Concurrent, so one sick broker cannot hold up every other container.
        await asyncio.gather(*(_reap(grouped, key) for key in grouped))


reap_streaming_sessions_task = ReapStreamingSessionsTask()
