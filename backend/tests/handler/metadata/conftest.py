from unittest.mock import AsyncMock

from utils.cache import VersionedCacheStore


def schema_stamp_get(*stores: VersionedCacheStore) -> AsyncMock:
    """Mock `async_cache.get` so the given stores read as currently stamped."""
    stamps = {store.schema_key: str(store.version) for store in stores}

    async def get(key: str) -> str | None:
        return stamps.get(key)

    return AsyncMock(side_effect=get)
