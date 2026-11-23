import hashlib
import json
from itertools import batched
from pathlib import Path
from typing import NamedTuple

from anyio import open_file
from redis.asyncio import Redis as AsyncRedis

from logger.logger import log


async def conditionally_set_cache(cache: AsyncRedis, key: str, file_path: Path) -> None:
    """Set the content of a JSON file to the cache, if it does not already exist or is outdated.

    The MD5 hash of the file is stored alongside the data to determine if the content has changed.
    """

    hash_key = f"{key}:file_hash"

    try:
        # Calculate file's MD5 hash to determine if content has changed.
        async with await open_file(file_path, "rb") as file:
            file_content = await file.read()
            md5_h = hashlib.md5(usedforsecurity=False)
            md5_h.update(file_content)
            file_hash = md5_h.hexdigest().lower()

        # If cache key exists, and hash matches, do nothing.
        data_exists = await cache.exists(key)
        cached_hash = await cache.get(hash_key)
        if data_exists and cached_hash == file_hash:
            log.debug(f"Cache is up to date, skipping initialization for {key}")
            return

        # Set the content of the file to the cache, and update the hash.
        index_data = json.loads(file_content)
        async with cache.pipeline() as pipe:
            # Clear existing data to avoid stale entries.
            if data_exists:
                await pipe.delete(key)
            for data_batch in batched(index_data.items(), 2000, strict=False):
                data_map = {k: json.dumps(v) for k, v in data_batch}
                await pipe.hset(key, mapping=data_map)
            await pipe.set(hash_key, file_hash)
            await pipe.execute()
            log.debug(
                f"Cache successfully set for {key}, total items: {len(index_data)}"
            )
    except Exception as e:
        # Log the error but don't fail - this allows migrations to run even if Redis is not available
        log.warning(f"Failed to initialize cache for {key}: {e}")


class VersionedCacheStore(NamedTuple):
    """A group of cache keys filled together, stamped with the shape they hold.

    Bump `version` when an import changes that shape, so a store an older
    release wrote is dropped rather than read as the current one.
    """

    schema_key: str
    version: int
    keys: tuple[str, ...]


async def is_cache_schema_current(
    cache: AsyncRedis, store: VersionedCacheStore
) -> bool:
    """Whether the store holds the shape its readers expect."""
    return await cache.get(store.schema_key) == str(store.version)


async def stamp_cache_schema(cache: AsyncRedis, store: VersionedCacheStore) -> None:
    """Record the shape a completed import left the store in."""
    await cache.set(store.schema_key, str(store.version))


async def is_cache_store_ready(
    cache: AsyncRedis, store: VersionedCacheStore, data_key: str
) -> bool:
    """Whether `data_key` holds entries an import wrote under the current shape.

    The stamp alone would trust a hash an eviction policy has since reclaimed.
    """
    if not await is_cache_schema_current(cache, store):
        return False

    return bool(await cache.exists(data_key))


async def drop_stale_cache_store(cache: AsyncRedis, store: VersionedCacheStore) -> bool:
    """Delete a store an older release wrote, returning whether one was there.

    `unlink` frees the hundreds of MB a metadata store holds off the main
    thread, so a boot does not stall every other client.
    """
    if await is_cache_schema_current(cache, store):
        return False

    dropped = await cache.unlink(*store.keys)
    await cache.unlink(store.schema_key)
    return bool(dropped)
