from enum import Enum

from config import ENABLE_EXPERIMENTAL_REDIS, REDIS_HOST, REDIS_PASSWORD, REDIS_PORT
from logger.logger import log
from redis import Redis
from rq import Queue


class QueuePrio(Enum):
    HIGH = "high"
    DEFAULT = "default"
    LOW = "low"


class FallbackCache:
    def __init__(self) -> None:
        self.fallback: dict = {}

    def get(self, key: str, *args, **kwargs) -> str:
        return self.fallback.get(key, "")

    def set(self, key: str, value: str, *args, **kwargs) -> None:
        self.fallback[key] = value

    def delete(self, key: str, *args, **kwargs) -> None:
        self.fallback.pop(key, None)

    def exists(self, key: str, *args, **kwargs) -> bool:
        return key in self.fallback

    def flushall(self) -> None:
        self.fallback = {}

    def __repr__(self) -> str:
        return f"<FallbackCache {self.fallback}>"

    def __str__(self) -> str:
        return repr(self)


redis_client = Redis(
    host=REDIS_HOST, port=int(REDIS_PORT), password=REDIS_PASSWORD, db=0
)

redis_url = (
    f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}"
    if REDIS_PASSWORD
    else f"redis://{REDIS_HOST}:{REDIS_PORT}"
)

high_prio_queue = Queue(name=QueuePrio.HIGH.value, connection=redis_client)
default_queue = Queue(name=QueuePrio.DEFAULT.value, connection=redis_client)
low_prio_queue = Queue(name=QueuePrio.LOW.value, connection=redis_client)

# A seperate client that auto-decodes responses is needed
_cache_client = Redis(
    host=REDIS_HOST,
    port=int(REDIS_PORT),
    password=REDIS_PASSWORD,
    db=0,
    decode_responses=True,
)
_fallback_cache = FallbackCache()
if ENABLE_EXPERIMENTAL_REDIS:
    log.info("Redis enabled: Connecting...")
cache = _cache_client if ENABLE_EXPERIMENTAL_REDIS else _fallback_cache
