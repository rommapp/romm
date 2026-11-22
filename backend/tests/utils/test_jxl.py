from io import BytesIO
from unittest.mock import patch

import pytest
from PIL import Image, UnidentifiedImageError
from tests.utils.test_images import jxl_image_bytes

from utils.jxl import jxl_size


def _encode(size: tuple[int, int], container: bool) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, "red").save(
        buf, format="JXL", lossless=True, effort=1, use_container=container
    )
    return buf.getvalue()


def _codestream_header(width: int, height: int) -> bytes:
    """A codestream that declares a size and holds nothing else."""
    bits: list[int] = [0]  # not the small, multiple-of-8 form

    def put(value: int, count: int) -> None:
        bits.extend((value >> i) & 1 for i in range(count))

    put(3, 2)
    put(height - 1, 30)
    put(0, 3)  # explicit width
    put(3, 2)
    put(width - 1, 30)
    bits.extend([0] * (-len(bits) % 8))
    body = bytes(
        sum(bit << i for i, bit in enumerate(bits[n : n + 8]))
        for n in range(0, len(bits), 8)
    )
    return b"\xff\x0a" + body + b"\x00" * 16


# Small 8-multiples, ratio-derived widths (4:3, 16:9, 2:1, 12:10) and explicit ones.
@pytest.mark.parametrize(
    "size",
    [
        (1, 1),
        (64, 64),
        (16, 24),
        (640, 480),
        (1920, 1080),
        (4000, 2000),
        (1200, 1000),
        (100, 37),
        (65, 9000),
    ],
)
@pytest.mark.parametrize("container", [False, True], ids=["codestream", "container"])
def test_jxl_size_matches_the_decoded_size(size: tuple[int, int], container: bool):
    data = _encode(size, container)

    assert jxl_size(data) == size
    with Image.open(BytesIO(data)) as img:
        assert img.size == size


def test_jxl_size_ignores_other_formats():
    buf = BytesIO()
    Image.new("RGB", (4, 4)).save(buf, format="PNG")

    assert jxl_size(buf.getvalue()) is None


def test_an_oversized_header_is_refused_before_decoding():
    data = _codestream_header(1 << 30, 1 << 30)

    assert jxl_size(data) == (1 << 30, 1 << 30)
    with patch("pillow_jxl.JpegXLImagePlugin.Decoder") as decoder:
        with pytest.raises(Image.DecompressionBombError):
            Image.open(BytesIO(data))
    decoder.assert_not_called()


def test_a_truncated_jxl_is_unidentified_rather_than_a_runtime_error():
    data = jxl_image_bytes()

    with pytest.raises(UnidentifiedImageError):
        Image.open(BytesIO(data[: len(data) // 2]))
