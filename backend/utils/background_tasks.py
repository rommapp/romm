import asyncio
from collections.abc import Coroutine
from typing import Any

# The event loop only holds weak refs to tasks; hold strong refs until they finish.
_background_tasks: set[asyncio.Task[Any]] = set()


def fire_and_forget(coro: Coroutine[Any, Any, Any]) -> None:
    """Schedule a coroutine without awaiting it."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
