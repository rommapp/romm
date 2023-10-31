from redis import Redis

from config import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, ENABLE_EXPERIMENTAL_REDIS


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


# A seperate client that auto-decodes responses is needed
_cache_client = Redis(
    host=REDIS_HOST,
    port=int(REDIS_PORT),
    password=REDIS_PASSWORD,
    db=0,
    decode_responses=True,
)
_fallback_cache = FallbackCache()
cache = _cache_client if ENABLE_EXPERIMENTAL_REDIS else _fallback_cache
