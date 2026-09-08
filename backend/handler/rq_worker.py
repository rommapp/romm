import logging
from typing import Any

import rq.scheduler
from rq import Worker

# Lines RQ emits on every maintenance sweep or scheduler tick. The work itself
# still runs (crash recovery for orphaned jobs, TTL reaping, stale worker
# pruning, scheduler lock renewal); only the records are dropped so they do not
# flood the logs, which at DEBUG means two heartbeat lines per second.
_PERIODIC_NOISE = (
    "cleaning registries for queue",
    "scheduler sending heartbeat to",
)


class _DropPeriodicNoiseFilter(logging.Filter):
    """Drops RQ's per-tick maintenance and scheduler-heartbeat log lines."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage().lower()
        return not any(fragment in message for fragment in _PERIODIC_NOISE)


def _silence_periodic_noise(logger: logging.Logger) -> None:
    if not any(isinstance(f, _DropPeriodicNoiseFilter) for f in logger.filters):
        logger.addFilter(_DropPeriodicNoiseFilter())


class RomMWorker(Worker):
    """RQ worker that silences RQ's noisy periodic log lines."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        _silence_periodic_noise(self.log)
        # --with-scheduler forks a scheduler off this process, so the filter it
        # inherits here is the only chance to configure that logger.
        _silence_periodic_noise(logging.getLogger(rq.scheduler.__name__))
