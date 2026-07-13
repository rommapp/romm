import logging
from typing import Any

from rq import Worker


class _DropRegistryCleanupFilter(logging.Filter):
    """Drops RQ's periodic "cleaning registries for queue" INFO line.

    The maintenance sweep still runs (crash recovery for orphaned jobs, TTL
    reaping, stale worker pruning); only its log record is suppressed so it
    does not flood logs on every maintenance interval.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return "cleaning registries for queue" not in record.getMessage()


class RomMWorker(Worker):
    """RQ worker that silences the noisy registry-cleanup log line."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if not any(isinstance(f, _DropRegistryCleanupFilter) for f in self.log.filters):
            self.log.addFilter(_DropRegistryCleanupFilter())
