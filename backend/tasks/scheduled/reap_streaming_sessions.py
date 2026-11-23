import asyncio

from handler.streaming.config import (
    ResolvedContainer,
    container_for_session,
    containers_by_key,
    streaming_enabled,
)
from handler.streaming.lifecycle import teardown_abandoned_session
from handler.streaming.session_store import (
    get_abandoned_session,
    in_restart_grace,
)
from logger.logger import log
from tasks.registry import REAP_STREAMING_SESSIONS_SPEC
from tasks.tasks import PeriodicTask


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
    def __init__(self) -> None:
        super().__init__(REAP_STREAMING_SESSIONS_SPEC)

    async def run(self) -> None:
        if not streaming_enabled() or await in_restart_grace():
            return

        # Empty once streaming is disabled, so a disabled install reaps nothing.
        grouped = containers_by_key()
        # Concurrent, so one sick broker cannot hold up every other container.
        await asyncio.gather(*(_reap(grouped, key) for key in grouped))


reap_streaming_sessions_task = ReapStreamingSessionsTask()
