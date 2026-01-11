import os
import sys
from enum import Enum

from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from rq import Queue
from rq.exceptions import DeserializationError
from rq.job import Job

from config import IS_PYTEST_RUN, REDIS_URL
from logger.logger import log


class QueuePrio(Enum):
    HIGH = "high"
    DEFAULT = "default"
    LOW = "low"


if IS_PYTEST_RUN:
    # Only import fakeredis when running tests, as it is a test dependency.
    from fakeredis import FakeRedis

    redis_client = FakeRedis(version=7)
else:
    redis_client = Redis.from_url(REDIS_URL)

high_prio_queue = Queue(name=QueuePrio.HIGH.value, connection=redis_client)
default_queue = Queue(name=QueuePrio.DEFAULT.value, connection=redis_client)
low_prio_queue = Queue(name=QueuePrio.LOW.value, connection=redis_client)


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
