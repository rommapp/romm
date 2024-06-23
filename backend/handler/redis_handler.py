import sys
from enum import Enum

from config import REDIS_DB, REDIS_HOST, REDIS_PASSWORD, REDIS_PORT, REDIS_USERNAME
from logger.logger import log
from redis import Redis, StrictRedis
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


def __get_cache() -> StrictRedis:
    if "pytest" in sys.modules:
        # Only import fakeredis when running tests, as it is a test dependency.
        from fakeredis import FakeStrictRedis

        return FakeStrictRedis(version=7)

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


cache = __get_cache()
