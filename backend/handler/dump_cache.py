"""Storage codec for the metadata dumps that live only in the cache.

Values are compressed one at a time because the stores are read by exact key.
"""

import json
from typing import Any, Final

import zstandard

from handler.redis_handler import async_binary_cache

# The stores these dumps live in. Their one home: the importers write them, the
# lookups read them, and `tools/measure_dump_cache.py` rebuilds them.
LAUNCHBOX_PLATFORMS_KEY: Final[str] = "romm:launchbox_platforms"
LAUNCHBOX_METADATA_DATABASE_ID_KEY: Final[str] = "romm:launchbox_metadata_database_id"
LAUNCHBOX_METADATA_NAME_KEY: Final[str] = "romm:launchbox_metadata_name"
LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY: Final[str] = (
    "romm:launchbox_metadata_alternate_name"
)
LAUNCHBOX_METADATA_FOLDED_NAME_KEY: Final[str] = "romm:launchbox_metadata_folded_name"
LAUNCHBOX_METADATA_IMAGE_KEY: Final[str] = "romm:launchbox_metadata_image"
LAUNCHBOX_MAME_KEY: Final[str] = "romm:launchbox_mame"
LAUNCHBOX_FILES_KEY: Final[str] = "romm:launchbox_files"
SWITCH_TITLEDB_INDEX_KEY: Final[str] = "romm:switch_titledb"
SWITCH_PRODUCT_ID_KEY: Final[str] = "romm:switch_product_id"

DUMP_STORE_KEYS: Final[tuple[str, ...]] = (
    LAUNCHBOX_PLATFORMS_KEY,
    LAUNCHBOX_METADATA_DATABASE_ID_KEY,
    LAUNCHBOX_METADATA_NAME_KEY,
    LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY,
    LAUNCHBOX_METADATA_FOLDED_NAME_KEY,
    LAUNCHBOX_METADATA_IMAGE_KEY,
    LAUNCHBOX_MAME_KEY,
    LAUNCHBOX_FILES_KEY,
    SWITCH_TITLEDB_INDEX_KEY,
    SWITCH_PRODUCT_ID_KEY,
)

# Level 3 costs less per read than the `json.loads` that follows it.
COMPRESSION_LEVEL: Final[int] = 3

# Below this a frame header and a poor ratio cost more than they save, which is
# what leaves the id-valued title and product id indexes as plain JSON.
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
