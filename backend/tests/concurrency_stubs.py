"""Helpers for tests that check which awaits overlap."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any


class InFlight:
    """Counts overlapping calls, holding each one long enough to overlap."""

    def __init__(self) -> None:
        self.current = 0
        self.peak = 0

    def enter(self) -> None:
        self.current += 1
        self.peak = max(self.peak, self.current)

    def leave(self) -> None:
        self.current -= 1

    async def hold(self, seconds: float = 0.01) -> None:
        self.enter()
        try:
            await asyncio.sleep(seconds)
        finally:
            self.leave()

    def returning(self, value: Any) -> Callable[..., Awaitable[Any]]:
        async def call(*_args: Any, **_kwargs: Any) -> Any:
            await self.hold()
            return value

        return call
