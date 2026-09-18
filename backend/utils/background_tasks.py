import asyncio
from collections.abc import Coroutine
from typing import Any

# The event loop only holds weak refs to tasks; hold strong refs until they finish.
_background_tasks: set[asyncio.Task[Any]] = set()


def fire_and_forget(coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
    """Schedule a coroutine without awaiting it."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def wait_for_background_tasks() -> None:
    """Await every task scheduled on this loop, for a caller whose loop stops when it returns."""
    loop = asyncio.get_running_loop()
    while pending := [task for task in _background_tasks if task.get_loop() is loop]:
        await asyncio.gather(*pending, return_exceptions=True)
