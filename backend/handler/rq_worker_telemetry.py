"""OpenTelemetry for RQ workers, imported only when telemetry is on."""

import contextlib
import os
import weakref
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

import psutil
from opentelemetry import metrics
from opentelemetry.metrics import CallbackOptions, Observation
from rq import Queue
from rq.job import Job

if TYPE_CHECKING:
    from handler.rq_worker import RomMWorker

_meter = metrics.get_meter(__name__)
_live_workers: "weakref.WeakSet[RomMWorker]" = weakref.WeakSet()

# The kernel tracks each work horse's peak, so it holds even for an OOM kill.
# A horse is a fork of its worker, so the peak includes the pages they share.
_job_peak_rss = _meter.create_histogram(
    "romm.rq.job.peak_rss",
    unit="By",
    description="Peak resident memory of the work horse that ran a job",
    # The default buckets end at 10,000, which every byte count overflows.
    explicit_bucket_boundaries_advisory=[
        mib * 1024 * 1024
        for mib in (64, 128, 192, 256, 384, 512, 768, 1024, 2048, 4096)
    ],
)


def _job_func_name(job: Job) -> str:
    # job.func_name unpickles the job's arguments, which imports every class they
    # name into the worker for good. RQ's text description starts with the name.
    return (job.description or "").partition("(")[0] or "unknown"


def _job_attributes(job: Job, queue: Queue) -> dict[str, str]:
    return {
        "messaging.system": "rq",
        "messaging.destination.name": queue.name,
        "rq.job.func_name": _job_func_name(job),
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


def _stop_metrics_in_forked_child() -> None:
    """Stop a worker's forked children (horses, its scheduler) exporting metrics."""
    # A child exports under its own pid but keeps the worker's metric totals, so
    # it would repeat them. Each work horse is measured by its worker instead.
    if not any(worker._worker_pid != os.getpid() for worker in list(_live_workers)):
        return
    provider = metrics.get_meter_provider()
    # The SDK can't stop a reader without one last export, so close the
    # exporters first and that export is dropped.
    for reader in list(getattr(provider, "_all_metric_readers", ())):
        with contextlib.suppress(Exception):
            reader._exporter.shutdown()
    shutdown = getattr(provider, "shutdown", None)
    if shutdown is not None:
        with contextlib.suppress(Exception):
            shutdown(timeout_millis=1000)


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_stop_metrics_in_forked_child)


def track(worker: "RomMWorker") -> None:
    """Sample this worker's horses, and stop its forked children exporting metrics."""
    _live_workers.add(worker)


def record_peak(job: Job, queue: Queue, stat: int | None, rusage: Any) -> None:
    killed = stat is not None and os.WIFSIGNALED(stat)
    _job_peak_rss.record(
        # ru_maxrss is in KiB on Linux.
        rusage.ru_maxrss * 1024,
        {**_job_attributes(job, queue), "rq.job.killed": killed},
    )
