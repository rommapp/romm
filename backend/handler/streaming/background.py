"""Fire-and-forget sync tasks, held so the event loop keeps them alive."""

import asyncio
from typing import Any

_sync_tasks: set[asyncio.Task] = set()


def spawn_sync_task(coro: Any) -> asyncio.Task:
    task = asyncio.get_running_loop().create_task(coro)
    _sync_tasks.add(task)
    task.add_done_callback(_sync_tasks.discard)
    return task
