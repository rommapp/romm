import contextlib
import logging
import os
import sys
import weakref
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Final, cast

import psutil
import rq.scheduler
from opentelemetry import metrics, trace
from opentelemetry.metrics import CallbackOptions, Observation
from opentelemetry.trace import SpanKind
from rq import Queue, Worker, worker_registration
from rq.callbacks import execute_failure_callback
from rq.exceptions import AbandonedJobError
from rq.executions import Execution
from rq.job import Job

from handler.redis_handler import get_job_func_name
from tasks.tasks import report_task_failure

if TYPE_CHECKING:
    from redis.client import Pipeline
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


_tracer = trace.get_tracer(__name__)
_meter = metrics.get_meter(__name__)
_live_workers: "weakref.WeakSet[RomMWorker]" = weakref.WeakSet()

# The kernel's peak for the whole horse, so it holds even when the horse was
# OOM-killed. A horse starts as a fork of its worker, so it includes those pages.
_job_peak_rss = _meter.create_histogram(
    "romm.rq.job.peak_rss",
    unit="By",
    description="Peak resident memory of the work horse that ran a job",
)


def _job_attributes(job: Job, queue: Queue) -> dict[str, str]:
    return {
        "messaging.system": "rq",
        "messaging.destination.name": queue.name,
        "rq.job.func_name": get_job_func_name(job, "unknown"),
    }


def _observe_horse_rss(_: CallbackOptions) -> Iterable[Observation]:
    for worker in list(_live_workers):
        monitored = worker.monitored_job
        if monitored is None or not worker.horse_pid:
            continue
        with contextlib.suppress(psutil.Error):
            rss = psutil.Process(worker.horse_pid).memory_info().rss
            yield Observation(rss, _job_attributes(*monitored))


_meter.create_observable_gauge(
    "romm.rq.horse.rss",
    [_observe_horse_rss],
    unit="By",
    description="Resident memory of each running work horse, sampled by its worker",
)


def _stop_inherited_metrics() -> None:
    """Stop the horse re-exporting its worker's metrics under the worker's pid.

    The worker measures the horse from outside, so nothing is lost. Capped so a
    down collector can't hold up the job.
    """
    shutdown = getattr(metrics.get_meter_provider(), "shutdown", None)
    if shutdown is not None:
        with contextlib.suppress(Exception):
            shutdown(timeout_millis=1000)


def _flush_spans() -> None:
    """Export the horse's spans; RQ ends it with os._exit, which skips atexit."""
    flush = getattr(trace.get_tracer_provider(), "force_flush", None)
    if flush is not None:
        with contextlib.suppress(Exception):
            flush(timeout_millis=2000)


def _database_engine() -> "Engine | None":
    return cast(
        "Engine | None", getattr(sys.modules.get(_DATABASE_MODULE), "sync_engine", None)
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
    """RQ worker that reports failed tasks, closes each work horse's database
    connections, silences RQ's periodic log lines, and registers again when its
    registration expires."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        _silence_periodic_noise(self.log)
        # --with-scheduler forks the scheduler off this process, so a filter
        # added here is the only one that logger inherits.
        _silence_periodic_noise(logging.getLogger(rq.scheduler.__name__))
        self.push_exc_handler(report_task_failure)
        self._inherited_db_pool: Pool | None = None
        self._worker_pid = os.getpid()
        self.monitored_job: tuple[Job, Queue] | None = None
        _live_workers.add(self)

    def heartbeat(
        self, timeout: int | None = None, pipeline: "Pipeline | None" = None
    ) -> None:
        super().heartbeat(timeout, pipeline)
        # A pipelined heartbeat cannot read Redis; the next plain one catches up.
        if (
            pipeline is None
            and self.birth_date is not None
            and not self._is_registered()
        ):
            self.log.warning(
                "Worker %s: registration expired, registering again", self.name
            )
            self._register_again()

    def _is_registered(self) -> bool:
        # A suspended host lets the key lapse: either the registry sweep drops the
        # worker from its sets, or the heartbeat recreates the key without queues.
        if not self.connection.hexists(self.key, "queues"):
            return False
        registries = [self.redis_workers_keys] + [
            worker_registration.WORKERS_BY_QUEUE_KEY % name
            for name in self.queue_names()
        ]
        return all(
            self.connection.sismember(registry, self.key) for registry in registries
        )

    def _register_again(self) -> None:
        # register_birth() refuses a key the heartbeat recreated, and would reset
        # the birth date. The heartbeat has already set the key's TTL.
        with self.connection.pipeline() as pipeline:
            pipeline.hset(
                self.key, mapping={**self.serialize(), "state": self.get_state()}
            )
            worker_registration.register(self, pipeline)
            pipeline.execute()

    def monitor_work_horse(self, job: Job, queue: Queue, execution: Execution) -> None:
        self.monitored_job = (job, queue)
        try:
            super().monitor_work_horse(job, queue, execution)
        finally:
            self.monitored_job = None

    def wait_for_horse(self) -> tuple[int | None, int | None, Any]:
        pid, stat, rusage = super().wait_for_horse()
        # The kill path waits a second time, after the horse was already reaped.
        if rusage is not None and self.monitored_job is not None:
            killed = stat is not None and os.WIFSIGNALED(stat)
            _job_peak_rss.record(
                # ru_maxrss is in KiB on Linux.
                rusage.ru_maxrss * 1024,
                {**_job_attributes(*self.monitored_job), "rq.job.killed": killed},
            )
        return pid, stat, rusage

    def perform_job(self, job: Job, queue: Queue, execution: Execution) -> bool:
        in_horse = os.getpid() != self._worker_pid
        if in_horse:
            _stop_inherited_metrics()
        engine = _database_engine()
        if engine is not None:
            # The forked pool holds the worker's connections. Closing them, or letting
            # them be garbage-collected, would end the worker's sessions.
            self._inherited_db_pool = engine.pool
            engine.dispose(close=False)
        try:
            with _tracer.start_as_current_span(
                f"process {queue.name}",
                kind=SpanKind.CONSUMER,
                attributes={
                    **_job_attributes(job, queue),
                    "messaging.operation.type": "process",
                    "messaging.message.id": job.id,
                },
            ):
                return super().perform_job(job, queue, execution)
        finally:
            # RQ exits the work horse with os._exit, bypassing pool finalizers.
            engine = _database_engine()
            if engine is not None:
                try:
                    engine.dispose()
                except Exception:
                    self.log.exception("Could not close the work horse database pool")
            if in_horse:
                _flush_spans()

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
            execute_failure_callback(job, self.death_penalty_class, *exc_info)
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
