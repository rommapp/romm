import asyncio

import pytest

from utils.concurrency import gather_all


async def test_gather_all_waits_for_every_awaitable_before_raising():
    finished = asyncio.Event()

    async def failing() -> None:
        raise ValueError("first")

    async def slow() -> None:
        await asyncio.sleep(0.01)
        finished.set()

    with pytest.raises(ValueError, match="first"):
        await gather_all(failing(), slow())

    assert finished.is_set()


async def test_gather_all_keeps_the_order_of_its_results():
    async def value(result: int, delay: float) -> int:
        await asyncio.sleep(delay)
        return result

    assert await gather_all(value(1, 0.02), value(2, 0)) == [1, 2]
