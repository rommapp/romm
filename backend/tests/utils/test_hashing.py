import re

from hypothesis import given
from hypothesis import strategies as st

from utils.hashing import crc32_to_hex

HEX_8 = re.compile(r"^[0-9a-f]{8}$")


@given(st.integers(min_value=0, max_value=2**32 - 1))
def test_crc32_to_hex_is_8_lowercase_hex_chars(value: int):
    result = crc32_to_hex(value)
    assert HEX_8.match(result)


@given(st.integers())
def test_crc32_to_hex_roundtrips_modulo_32_bits(value: int):
    result = crc32_to_hex(value)
    assert int(result, 16) == value & 0xFFFFFFFF
