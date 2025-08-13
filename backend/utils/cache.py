import json
from itertools import batched
from pathlib import Path

from anyio import open_file
from logger.logger import log
from redis.asyncio import Redis as AsyncRedis


async def conditionally_set_cache(cache: AsyncRedis, key: str, file_path: Path) -> None:
    """Set the content of a JSON file to the cache, if it does not already exist."""
    try:
        if await cache.exists(key):
            return
        async with await open_file(file_path, "r") as file:
            index_data = json.loads(await file.read())
            async with cache.pipeline() as pipe:
                for data_batch in batched(index_data.items(), 2000, strict=False):
                    data_map = {k: json.dumps(v) for k, v in dict(data_batch).items()}
                    await pipe.hset(key, mapping=data_map)
                await pipe.execute()
    except Exception as e:
        # Log the error but don't fail - this allows migrations to run even if Redis is not available
        log.warning(f"Failed to initialize cache for {key}: {e}")
