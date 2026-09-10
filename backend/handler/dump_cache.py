"""Storage codec for the metadata dumps that live only in the cache.

The LaunchBox and Switch TitleDB stores hold hundreds of MB of JSON that is
only ever read by exact key, so each value is compressed on its own rather
than as a stream. Reads detect the frame instead of trusting the key, so a
store written before this keeps answering until the next import rewrites it.
"""

import json
from typing import Any, Final

import zstandard

from handler.redis_handler import async_binary_cache

# Level 3 adds 3-6us per record read, less than the `json.loads` that follows
# it, and 1.8x on the real dumps.
COMPRESSION_LEVEL: Final[int] = 3

# Under this size a frame header and a poor ratio on a short payload cost more
# than they save, which is what keeps the id-valued title and product id
# indexes stored as plain JSON. `tools/measure_dump_cache.py --sweep` finds the
# real records flat between 64 and 256, so this sits at the top of that range.
COMPRESS_MIN_BYTES: Final[int] = 256

# Zstandard frame magic, from RFC 8878 section 3.1.1.
_ZSTD_MAGIC: Final[bytes] = b"\x28\xb5\x2f\xfd"

_compressor = zstandard.ZstdCompressor(level=COMPRESSION_LEVEL)
_decompressor = zstandard.ZstdDecompressor()


def encode(value: Any) -> bytes:
    """Serialize a dump record, compressing it when it is large enough to pay off.

    Args:
        value: The record to store, as JSON-serializable data.

    Returns:
        The bytes to write into the store.
    """
    payload = json.dumps(value, separators=(",", ":")).encode()
    if len(payload) < COMPRESS_MIN_BYTES:
        return payload

    return _compressor.compress(payload)


def decode(raw: bytes | str | None) -> Any:
    """Deserialize a dump record, whether or not it was stored compressed.

    Args:
        raw: The stored bytes, or None when the field is absent.

    Returns:
        The record, or None when there was nothing stored.
    """
    if not raw:
        return None

    if isinstance(raw, bytes) and raw.startswith(_ZSTD_MAGIC):
        raw = _decompressor.decompress(raw)

    return json.loads(raw)


async def hget_json(key: str, field: str) -> Any:
    """Read one record out of a dump store.

    Args:
        key: The store's cache key.
        field: The field to read.

    Returns:
        The record, or None when the field is absent.
    """
    return decode(await async_binary_cache.hget(key, field))
