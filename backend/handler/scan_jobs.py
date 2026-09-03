"""Finding and pruning the RQ jobs that run a library scan."""

from datetime import datetime, timedelta, timezone
from itertools import chain
from typing import Final

from rq import Worker
from rq.job import Job, JobStatus
from rq.registry import ScheduledJobRegistry

from handler.redis_handler import (
    cancel_job,
    get_job_func_name,
    get_job_kwargs,
    get_job_status,
    get_worker_current_job,
    high_prio_queue,
    low_prio_queue,
    redis_client,
    scan_queue,
)
from logger.logger import log
from tasks.tasks import TaskType

# The name RQ records for a directly enqueued scan, kept in step with the
# function by a test rather than an import, which would be a cycle.
SCAN_PLATFORMS_FUNC: Final = "endpoints.sockets.scan.scan_platforms"

# A delayed watcher scan this far past due was left behind by an instance that
# was not running, and the change it reacted to has long since settled.
STALE_SCHEDULED_SCAN_AGE: Final = timedelta(hours=1)


def is_scan_job(job: Job) -> bool:
    """Whether this job runs a scan.

    Task-driven scans carry the task runner's func name, which every task
    shares, so those are recognised by the type in their meta instead.
    """
    if get_job_func_name(job) == SCAN_PLATFORMS_FUNC:
        return True

    return job.meta.get("task_type") == TaskType.SCAN


def is_scoped_scan_job(job: Job) -> bool:
    """Whether this scan covers named roms rather than the library.

    A scan that cannot be read is treated as a library scan: the worker will
    fail it on the next dequeue, so it stops standing in the way by itself.
    """
    kwargs = get_job_kwargs(job)
    return bool(kwargs and kwargs.get("roms_ids"))


def get_running_scan_job() -> Job | None:
    """The scan currently executing on a worker, if any.

    A started job is no longer in the queue, so it can only be found by asking
    the workers what they are holding.
    """
    for worker in Worker.all(connection=redis_client):
        job = get_worker_current_job(worker)
        if job is not None and is_scan_job(job):
            return job

    return None


def get_queued_scan_jobs() -> list[Job]:
    """Scans sitting on a worker queue, waiting to be picked up.

    A scan enqueued by an older release sits on one of the other queues, where
    a worker will still run it.
    """
    job_ids = chain(
        scan_queue.get_job_ids(),
        high_prio_queue.get_job_ids(),
        low_prio_queue.get_job_ids(),
    )
    jobs = Job.fetch_many(job_ids, connection=redis_client)

    return [
        job
        for job in jobs
        if job is not None and is_scan_job(job)
        # The fetch above already carries the status, so re-reading it would be
        # a round trip per queued job.
        and get_job_status(job, refresh=False) == JobStatus.QUEUED
    ]


def _scheduled_scan_registries() -> list[ScheduledJobRegistry]:
    """Where delayed scans wait until a worker releases them.

    A scan delayed by an older release waits in the low priority queue's
    registry, where a worker will still release it.
    """
    return [
        ScheduledJobRegistry(queue=scan_queue),
        ScheduledJobRegistry(queue=low_prio_queue),
    ]


def get_scheduled_scan_jobs() -> list[Job]:
    """Scans waiting out a delay, which only the watcher sets.

    These never stand in for a scan in flight: a worker has to be running to
    release them, so counting them would refuse scans on an idle instance.
    """
    job_ids = chain.from_iterable(
        registry.get_job_ids() for registry in _scheduled_scan_registries()
    )
    jobs = Job.fetch_many(job_ids, connection=redis_client)

    return [job for job in jobs if job is not None and is_scan_job(job)]


def get_blocking_library_scans() -> tuple[Job | None, list[Job]]:
    """The library scans a second one has to wait for: one running, any queued.

    A scan of named roms is not one of them. It resolves its work from the
    database and is done in seconds, so nothing has to queue behind it.
    """
    running = get_running_scan_job()
    if running is not None and is_scoped_scan_job(running):
        running = None

    queued = [job for job in get_queued_scan_jobs() if not is_scoped_scan_job(job)]

    return running, queued


def get_pending_scan_jobs() -> list[Job]:
    """Scans that have not started yet: queued, or waiting out a delay.

    A scan already running is deliberately not one of these. It may have walked
    past the folder that just changed, so a fresh scan is still warranted.
    """
    return get_queued_scan_jobs() + get_scheduled_scan_jobs()


def drop_stale_scheduled_scans() -> int:
    """Drop delayed watcher scans that are long past due.

    Releasing a backlog of them at once, which is what an instance that was down
    for a while does on start, would run the same library scan over and over.

    Returns:
        int: How many scans were dropped.
    """
    cutoff = datetime.now(timezone.utc) - STALE_SCHEDULED_SCAN_AGE

    # A registry is scored by due time, so it can hand back only what is due.
    stale_ids = chain.from_iterable(
        registry.get_jobs_to_schedule(int(cutoff.timestamp()))
        for registry in _scheduled_scan_registries()
    )
    jobs = Job.fetch_many(stale_ids, connection=redis_client)
    dropped = 0

    for job in jobs:
        if job is None or not is_scan_job(job):
            continue

        if not cancel_job(job):
            continue

        dropped += 1
        log.warning(
            f"Dropped scan {job.id}, overdue by more than {STALE_SCHEDULED_SCAN_AGE}"
        )

    return dropped
