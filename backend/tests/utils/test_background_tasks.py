import asyncio
from contextlib import suppress

from utils import background_tasks


async def test_waiting_skips_another_loops_tasks():
    """A task left on a loop that is not running can never finish."""
    other_loop = asyncio.new_event_loop()
    stranded = other_loop.create_task(asyncio.sleep(60))
    background_tasks._background_tasks.add(stranded)
    try:
        await asyncio.wait_for(background_tasks.wait_for_background_tasks(), timeout=1)
    finally:
        background_tasks._background_tasks.discard(stranded)
        stranded.cancel()
        with suppress(asyncio.CancelledError):
            await asyncio.to_thread(other_loop.run_until_complete, stranded)
        other_loop.close()


async def test_waiting_covers_tasks_spawned_while_waiting():
    finished = asyncio.Event()

    async def second() -> None:
        await asyncio.sleep(0.01)
        finished.set()

    async def first() -> None:
        await asyncio.sleep(0.01)
        background_tasks.fire_and_forget(second())

    background_tasks.fire_and_forget(first())
    await background_tasks.wait_for_background_tasks()

    assert finished.is_set()
