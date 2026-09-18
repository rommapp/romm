"""Fire-and-forget sync tasks, held so the event loop keeps them alive."""

import asyncio
from typing import Any

_sync_tasks: set[asyncio.Task] = set()


def spawn_sync_task(coro: Any) -> asyncio.Task:
    task = asyncio.get_running_loop().create_task(coro)
    _sync_tasks.add(task)
    task.add_done_callback(_sync_tasks.discard)
    return task


async def wait_for_sync_tasks() -> None:
    """Await every spawned task, for a caller whose loop stops when it returns."""
    while _sync_tasks:
        await asyncio.gather(*_sync_tasks, return_exceptions=True)
