import hashlib
import json
from itertools import batched
from pathlib import Path

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
