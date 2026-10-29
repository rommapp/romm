import contextlib
import logging
import sys
from typing import TYPE_CHECKING, Any, Final

import rq.scheduler
from rq import Queue, Worker
from rq.exceptions import AbandonedJobError
from rq.job import Job

from tasks.tasks import report_task_failure

if TYPE_CHECKING:
    from sqlalchemy import Engine, Pool

# Fragments of the lines RQ logs on every tick. The maintenance sweep and the
# scheduler heartbeat still run; only their log records are dropped.
_PERIODIC_NOISE: Final[tuple[str, ...]] = (
    "cleaning registries for queue",
    "scheduler sending heartbeat to",
)

# Looked up in sys.modules rather than imported, so a job that never loaded the
# ORM does not load it just to clean it up.
_DATABASE_MODULE: Final = "handler.database.base_handler"


def _database_engine() -> "Engine | None":
    engine: Engine | None = getattr(
        sys.modules.get(_DATABASE_MODULE), "sync_engine", None
    )
    return engine


class _DropPeriodicNoiseFilter(logging.Filter):
    """Drops RQ's per-tick maintenance and scheduler-heartbeat log lines."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage().lower()
        return not any(fragment in message for fragment in _PERIODIC_NOISE)


def _silence_periodic_noise(logger: logging.Logger) -> None:
    if not any(isinstance(f, _DropPeriodicNoiseFilter) for f in logger.filters):
        logger.addFilter(_DropPeriodicNoiseFilter())


class RomMWorker(Worker):
    """RQ worker that reports failed tasks, closes each work horse's database
    connections, and silences RQ's periodic log lines."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        _silence_periodic_noise(self.log)
        # --with-scheduler forks the scheduler off this process, so a filter
        # added here is the only one that logger inherits.
        _silence_periodic_noise(logging.getLogger(rq.scheduler.__name__))
        self.push_exc_handler(report_task_failure)
        self._inherited_db_pool: Pool | None = None

    def perform_job(self, job: Job, queue: Queue) -> bool:
        engine = _database_engine()
        if engine is not None:
            # The forked pool holds the worker's connections. Closing them, or letting
            # them be garbage-collected, would end the worker's sessions.
            self._inherited_db_pool = engine.pool
            engine.dispose(close=False)
        try:
            return super().perform_job(job, queue)
        finally:
            # RQ exits the work horse with os._exit, bypassing pool finalizers.
            engine = _database_engine()
            if engine is not None:
                try:
                    engine.dispose()
                except Exception:
                    self.log.exception("Could not close the work horse database pool")

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
