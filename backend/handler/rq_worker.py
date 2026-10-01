import contextlib
import logging
from typing import Any, Final

import rq.scheduler
from rq import Worker
from rq.exceptions import AbandonedJobError
from rq.job import Job

from tasks.tasks import report_task_failure

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
    """RQ worker that reports failed tasks and silences RQ's periodic log lines."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        _silence_periodic_noise(self.log)
        # --with-scheduler forks the scheduler off this process, so a filter
        # added here is the only one that logger inherits.
        _silence_periodic_noise(logging.getLogger(rq.scheduler.__name__))
        self.push_exc_handler(report_task_failure)

    def handle_work_horse_killed(
        self, job: Job, retpid: int, ret_val: int, rusage: Any
    ) -> None:
        # mypy's untyped_calls_exclude cannot name the receiver of a super() call.
        super().handle_work_horse_killed(job, retpid, ret_val, rusage)  # type: ignore[no-untyped-call]
        # RQ runs neither the failure callback nor the exception handlers for a
        # killed horse, only for a job whose whole worker died.
        exc_info = (AbandonedJobError, AbandonedJobError(), None)
        # RQ logs a callback that raises.
        with contextlib.suppress(Exception):
            job.execute_failure_callback(self.death_penalty_class, *exc_info)
        self.handle_exception(job, *exc_info)


class PreloadingWorker(RomMWorker):
    """RomMWorker that imports the enabled scheduled tasks of its queues up front.

    For a dedicated queue whose tasks run often enough that every work horse
    importing its task again costs more than holding it in the parent.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        from tasks.registry import SCHEDULED_TASKS, get_task

        queues = set(self.queue_names())
        for name, spec in SCHEDULED_TASKS.items():
            if spec.enabled and spec.queue_name in queues:
                get_task(name)
