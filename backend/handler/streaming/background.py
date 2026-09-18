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
    """Await every task spawned on this loop, for a caller whose loop stops when it returns."""
    loop = asyncio.get_running_loop()
    while pending := [task for task in _sync_tasks if task.get_loop() is loop]:
        await asyncio.gather(*pending, return_exceptions=True)
