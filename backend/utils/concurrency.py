import asyncio
from collections.abc import Awaitable
from typing import Any


async def gather_all(*aws: Awaitable[Any]) -> list[Any]:
    """Await every awaitable, leaving none running, then raise the first failure."""
    results = await asyncio.gather(*aws, return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            raise result
    return results
