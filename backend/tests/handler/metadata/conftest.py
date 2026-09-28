import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock

from utils.cache import VersionedCacheStore


def schema_stamp_get(*stores: VersionedCacheStore) -> AsyncMock:
    """Mock `async_cache.get` so the given stores read as currently stamped."""
    stamps = {store.schema_key: str(store.version) for store in stores}

    async def get(key: str) -> str | None:
        return stamps.get(key)

    return AsyncMock(side_effect=get)


@contextmanager
def local_timezone(name: str) -> Iterator[None]:
    """Pin the process timezone that a naive datetime.timestamp() reads."""
    previous = os.environ.get("TZ")
    os.environ["TZ"] = name
    time.tzset()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous
        time.tzset()
