import asyncio
import os
import sys
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any, Final, cast
from uuid import uuid4

from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from rq import Queue, Worker
from rq.exceptions import DeserializationError, InvalidJobOperation, NoSuchJobError
from rq.job import Job, JobStatus
from rq.worker import BaseWorker, WorkerStatus

from config import IS_PYTEST_RUN, REDIS_URL
from logger.logger import log


class QueuePrio(Enum):
    HIGH = "high"
    DEFAULT = "default"
    LOW = "low"


# Scans have a queue and a worker of their own: a library scan runs for hours,
# and one worker on one queue keeps two of them from ever running at once.
SCAN_QUEUE_NAME: Final = "scans"
# Streaming teardowns and exit save pulls get one too: a sick broker can hold
# either for minutes.
STREAMING_QUEUE_NAME: Final = "streaming"

redis_client = Redis.from_url(REDIS_URL)

high_prio_queue = Queue(name=QueuePrio.HIGH.value, connection=redis_client)
default_queue = Queue(name=QueuePrio.DEFAULT.value, connection=redis_client)
low_prio_queue = Queue(name=QueuePrio.LOW.value, connection=redis_client)
scan_queue = Queue(name=SCAN_QUEUE_NAME, connection=redis_client)
streaming_queue = Queue(name=STREAMING_QUEUE_NAME, connection=redis_client)

ALL_QUEUES: Final = (
    scan_queue,
    streaming_queue,
    high_prio_queue,
    default_queue,
    low_prio_queue,
)


def __get_fake_server() -> Any:
    # Only import fakeredis when running tests, as it is a test dependency.
    from fakeredis import FakeServer

    # One keyspace for both caches, as one Redis serves both outside tests, so
    # a flush between tests clears what either of them wrote.
    return FakeServer(version=(7,))


_fake_server = __get_fake_server() if IS_PYTEST_RUN else None


def __get_sync_cache() -> Redis:
    if IS_PYTEST_RUN:
        from fakeredis import FakeRedis

        return FakeRedis(server=_fake_server)

    # A separate client that auto-decodes responses is needed
    client = Redis.from_url(REDIS_URL, decode_responses=True)
    log.debug(
        f"Sync redis/valkey connection established in {os.path.splitext(os.path.basename(sys.argv[0]))[0]}"
    )
    return client


_LOOP_CLIENT_ATTR: Final = "_romm_fake_async_redis"


class _PerLoopFakeAsyncRedis:
    """A fake async client per event loop, all over the one fake server."""

    # Tests reach the cache from the TestClient's loop and from their own
    # asyncio.run loops at once, and a shared pool's asyncio.Lock binds to one.
    # Outside a loop, as in asyncio.run(async_cache.get(...)), each thread gets
    # its own client: one thread's loops run one at a time, so never contend.
    def __init__(self, server: Any) -> None:
        self._server = server
        self._by_thread = threading.local()

    def _new_client(self) -> Any:
        from fakeredis import FakeAsyncRedis

        return FakeAsyncRedis(server=self._server)

    def _client(self) -> Any:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            client = getattr(self._by_thread, "client", None)
            if client is None:
                client = self._by_thread.client = self._new_client()
            return client
        # Held on the loop, not in a map keyed by it: the client's asyncio
        # objects reference the loop, so such a map would never let one go.
        client = getattr(loop, _LOOP_CLIENT_ATTR, None)
        if client is None:
            client = self._new_client()
            setattr(loop, _LOOP_CLIENT_ATTR, client)
        return client

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client(), name)


def __get_async_cache() -> AsyncRedis:
    if IS_PYTEST_RUN:
        return cast(AsyncRedis, _PerLoopFakeAsyncRedis(_fake_server))

    # A separate client that auto-decodes responses is needed
    client = AsyncRedis.from_url(REDIS_URL, decode_responses=True)
    log.debug(
        f"Async redis/valkey connection established in {os.path.splitext(os.path.basename(sys.argv[0]))[0]}"
    )
    return client


sync_cache = __get_sync_cache()
async_cache = __get_async_cache()


def __get_async_binary_cache() -> AsyncRedis:
    """A client that leaves values as bytes, since `async_cache` decodes every
    response as UTF-8 and a zstd frame is not."""
    if IS_PYTEST_RUN:
        # The fake does not decode responses, which is what this client wants.
        return async_cache

    return AsyncRedis.from_url(REDIS_URL)


async_binary_cache = __get_async_binary_cache()


@asynccontextmanager
async def redis_lock(
    key: str, *, timeout_seconds: int, poll_seconds: float = 0.1
) -> AsyncIterator[None]:
    """Hold `key` as a mutex across gunicorn workers, via SET NX (no Lua needed).

    Raises:
        TimeoutError: The key stayed held for `timeout_seconds`.
    """
    token = uuid4().hex
    for _ in range(int(timeout_seconds / poll_seconds)):
        if await async_cache.set(key, token, nx=True, ex=timeout_seconds):
            break
        await asyncio.sleep(poll_seconds)
    else:
        raise TimeoutError(f"Timed out waiting for lock {key}")
    try:
        yield
    finally:
        # Only the owner releases; an expired lock may belong to someone else.
        held = await async_cache.get(key)
        if held in (token, token.encode()):
            await async_cache.delete(key)


def as_text(value: bytes | str) -> str:
    """A cached value as text, since the fake caches return bytes where Redis decodes."""
    return value.decode() if isinstance(value, bytes) else value


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


def get_worker_current_job(worker: BaseWorker) -> Job | None:
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


def has_live_worker(queue: Queue) -> bool:
    """Whether a job enqueued on ``queue`` would be picked up."""
    # A worker that crashed without announcing it stays registered until its
    # key TTL lapses, so this can still say yes for a few minutes after a kill.
    return any(
        worker.death_date is None and worker.get_state() != WorkerStatus.SUSPENDED
        for worker in Worker.all(queue=queue)
    )
