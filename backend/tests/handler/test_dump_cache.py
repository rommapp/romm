import json

import pytest

from handler.dump_cache import (
    _ZSTD_MAGIC,
    COMPRESS_MIN_BYTES,
    decode,
    encode,
    hget_json,
)
from handler.redis_handler import async_binary_cache

BIG_RECORD = {"Name": "Chrono Trigger", "Overview": "A long summary. " * 100}
SMALL_RECORD = "12345"


class TestEncode:
    def test_compresses_a_record_worth_compressing(self):
        stored = encode(BIG_RECORD)

        assert stored.startswith(_ZSTD_MAGIC)
        assert len(stored) < len(json.dumps(BIG_RECORD).encode())

    def test_leaves_a_short_value_as_plain_json(self):
        stored = encode(SMALL_RECORD)

        assert stored == b'"12345"'

    @pytest.mark.parametrize("payload_size", [2, COMPRESS_MIN_BYTES - 1])
    def test_stores_a_payload_under_the_threshold_verbatim(self, payload_size: int):
        # The threshold applies to the serialized payload, quotes included.
        value = "x" * (payload_size - 2)
        stored = encode(value)

        assert not stored.startswith(_ZSTD_MAGIC)
        assert json.loads(stored) == value

    def test_compresses_a_payload_at_the_threshold(self):
        value = "x" * (COMPRESS_MIN_BYTES - 2)

        assert encode(value).startswith(_ZSTD_MAGIC)


class TestDecode:
    @pytest.mark.parametrize("value", [BIG_RECORD, SMALL_RECORD, [], {}, 0])
    def test_round_trips_whatever_encode_wrote(self, value):
        assert decode(encode(value)) == value

    def test_reads_a_store_written_before_compression(self):
        """An existing store holds plain JSON, so it has to keep answering."""
        legacy = json.dumps(BIG_RECORD).encode()

        assert decode(legacy) == BIG_RECORD

    def test_reads_a_value_handed_over_as_text(self):
        """`fakeredis` and a decoding client both hand back `str`."""
        assert decode(json.dumps(BIG_RECORD)) == BIG_RECORD

    @pytest.mark.parametrize("missing", [None, b"", ""])
    def test_returns_nothing_for_an_absent_field(self, missing):
        assert decode(missing) is None


class TestHgetJson:
    @pytest.mark.asyncio
    async def test_reads_back_a_compressed_record(self):
        await async_binary_cache.hset(
            "romm:test_dump_cache", mapping={"1": encode(BIG_RECORD)}
        )

        assert await hget_json("romm:test_dump_cache", "1") == BIG_RECORD

    @pytest.mark.asyncio
    async def test_returns_none_for_a_field_that_is_not_there(self):
        assert await hget_json("romm:test_dump_cache", "absent") is None
