"""Streaming queue stub shared by the streaming endpoint and reaper tests."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock, patch

from handler.streaming import background


@contextmanager
def exit_pulls_spawned_inline() -> Iterator[MagicMock]:
    """Run each queued exit save pull as a spawned task, as no worker runs here."""

    def enqueue(func: Any, *, kwargs: dict[str, Any], **_: Any) -> None:
        background.spawn_sync_task(func(**kwargs))

    with patch("handler.streaming.lifecycle.streaming_queue") as queue:
        queue.enqueue.side_effect = enqueue
        yield queue
