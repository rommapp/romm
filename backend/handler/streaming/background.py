"""Fire-and-forget sync tasks, held so the event loop keeps them alive."""

import asyncio
from typing import Any

from utils.background_tasks import fire_and_forget


def spawn_sync_task(coro: Any) -> asyncio.Task:
    return fire_and_forget(coro)
