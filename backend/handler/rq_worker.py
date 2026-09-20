import logging
from typing import Any, Final

import rq.scheduler
from rq import Worker

# Fragments of the lines RQ logs on every tick. The maintenance sweep and the
# scheduler heartbeat still run; only their log records are dropped.
_PERIODIC_NOISE: Final[tuple[str, ...]] = (
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
        # --with-scheduler forks the scheduler off this process, so a filter
        # added here is the only one that logger inherits.
        _silence_periodic_noise(logging.getLogger(rq.scheduler.__name__))
