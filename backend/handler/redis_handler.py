import sys
from enum import Enum

from config import (
    IS_PYTEST_RUN,
    REDIS_DB,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
    REDIS_USERNAME,
)
from logger.logger import log
from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from rq import Queue


class QueuePrio(Enum):
    HIGH = "high"
    DEFAULT = "default"
    LOW = "low"


redis_client = Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    username=REDIS_USERNAME,
    db=REDIS_DB,
)
redis_url = (
    f"redis://{REDIS_USERNAME}:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    if REDIS_PASSWORD
    else f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
)

high_prio_queue = Queue(name=QueuePrio.HIGH.value, connection=redis_client)
default_queue = Queue(name=QueuePrio.DEFAULT.value, connection=redis_client)
low_prio_queue = Queue(name=QueuePrio.LOW.value, connection=redis_client)


def __get_sync_cache() -> Redis:
    if IS_PYTEST_RUN:
        # Only import fakeredis when running tests, as it is a test dependency.
        from fakeredis import FakeRedis

        return FakeRedis(version=7)

    log.info(f"Connecting to redis in {sys.argv[0]}...")
    # A separate client that auto-decodes responses is needed
    client = Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        username=REDIS_USERNAME,
        db=REDIS_DB,
        decode_responses=True,
    )
    log.info(f"Redis connection established in {sys.argv[0]}!")
    return client


def __get_async_cache() -> AsyncRedis:
    if IS_PYTEST_RUN:
        # Only import fakeredis when running tests, as it is a test dependency.
        from fakeredis import FakeAsyncRedis

        return FakeAsyncRedis(version=7)

    log.info(f"Connecting to redis in {sys.argv[0]}...")
    # A separate client that auto-decodes responses is needed
    client = AsyncRedis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        username=REDIS_USERNAME,
        db=REDIS_DB,
        decode_responses=True,
    )
    log.info(f"Redis connection established in {sys.argv[0]}!")
    return client


sync_cache = __get_sync_cache()
async_cache = __get_async_cache()
