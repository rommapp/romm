import os
import sys
from enum import Enum
from typing import Any, Final

from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from rq import Queue, Worker
from rq.exceptions import DeserializationError, InvalidJobOperation, NoSuchJobError
from rq.job import Job, JobStatus

from config import IS_PYTEST_RUN, REDIS_URL
from logger.logger import log


class QueuePrio(Enum):
    HIGH = "high"
    DEFAULT = "default"
    LOW = "low"


# Scans have a queue and a worker of their own: a library scan runs for hours,
# and one worker on one queue keeps two of them from ever running at once.
SCAN_QUEUE_NAME: Final = "scans"

redis_client = Redis.from_url(REDIS_URL)

high_prio_queue = Queue(name=QueuePrio.HIGH.value, connection=redis_client)
default_queue = Queue(name=QueuePrio.DEFAULT.value, connection=redis_client)
low_prio_queue = Queue(name=QueuePrio.LOW.value, connection=redis_client)
scan_queue = Queue(name=SCAN_QUEUE_NAME, connection=redis_client)

ALL_QUEUES: Final = (scan_queue, high_prio_queue, default_queue, low_prio_queue)


def __get_sync_cache() -> Redis:
    if IS_PYTEST_RUN:
        # Only import fakeredis when running tests, as it is a test dependency.
        from fakeredis import FakeRedis

        return FakeRedis(version=7)

    # A separate client that auto-decodes responses is needed
    client = Redis.from_url(REDIS_URL, decode_responses=True)
    log.debug(
        f"Sync redis/valkey connection established in {os.path.splitext(os.path.basename(sys.argv[0]))[0]}"
    )
    return client


def __get_async_cache() -> AsyncRedis:
    if IS_PYTEST_RUN:
        # Only import fakeredis when running tests, as it is a test dependency.
        from fakeredis import FakeAsyncRedis

        return FakeAsyncRedis(version=7)

    # A separate client that auto-decodes responses is needed
    client = AsyncRedis.from_url(REDIS_URL, decode_responses=True)
    log.debug(
        f"Async redis/valkey connection established in {os.path.splitext(os.path.basename(sys.argv[0]))[0]}"
    )
    return client


sync_cache = __get_sync_cache()
async_cache = __get_async_cache()


def get_job_func_name(job: Job, fallback: str = "") -> str:
    """Safely get the function name from an RQ job, handling DeserializationError.

    Args:
        job: The RQ Job object to get the function name from
        fallback: The value to return if deserialization fails

    Returns:
        The function name if available, otherwise the fallback value
    """
    try:
        return job.func_name or fallback
    except DeserializationError:
        # Job data cannot be deserialized (e.g., function no longer exists)
        return fallback


def get_job_status(job: Job, refresh: bool = True) -> JobStatus | None:
    """Safely get the status of an RQ job, which is gone once its hash expires.

    Args:
        job: The RQ Job object to get the status of
        refresh: Whether to re-read the status, rather than trust the one the
            job was fetched with

    Returns:
        The job status, or None if the job no longer has one
    """
    try:
        return job.get_status(refresh=refresh)
    except InvalidJobOperation:
        return None


def get_job_kwargs(job: Job) -> dict[str, Any] | None:
    """Safely get the keyword arguments an RQ job was enqueued with.

    Args:
        job: The RQ Job object to read

    Returns:
        The keyword arguments, or None if the payload cannot be deserialized
    """
    try:
        return job.kwargs
    except DeserializationError:
        return None


def cancel_job(job: Job) -> bool:
    """Cancel an RQ job, tolerating one that is already cancelled.

    Args:
        job: The RQ Job object to cancel

    Returns:
        Whether this call was the one that cancelled it
    """
    try:
        job.cancel()
    except InvalidJobOperation:
        return False

    return True


def get_worker_current_job(worker: Worker) -> Job | None:
    """Safely get the job a worker is holding, which can be gone before the
    worker's own registration expires.

    Args:
        worker: The RQ Worker to read

    Returns:
        The job the worker is running, or None if it has none or it is gone
    """
    try:
        return worker.get_current_job()
    except NoSuchJobError:
        return None
