"""JPEG XL support for Pillow, size-checked before any pixel is decoded.

pillow-jxl decodes the whole image while opening it, before Pillow's
decompression-bomb check sees the size, so this reads the dimensions from the
codestream header first and registers a guarded decoder in its place.
"""

import struct

from PIL import Image
from pillow_jxl.JpegXLImagePlugin import JXLImageFile, _accept

_CODESTREAM_SIGNATURE = b"\xff\x0a"
_CONTAINER_SIGNATURE = b"\x00\x00\x00\x0cJXL \x0d\x0a\x87\x0a"
# Width-to-height ratios a SizeHeader can name instead of storing the width.
_RATIOS = {
    1: (1, 1),
    2: (12, 10),
    3: (4, 3),
    4: (3, 2),
    5: (16, 9),
    6: (5, 4),
    7: (2, 1),
}


class _BitReader:
    """Reads the least-significant-bit-first fields of a JPEG XL header."""

    def __init__(self, data: bytes, offset: int) -> None:
        self._data = data
        self._pos = offset * 8

    def bits(self, count: int) -> int:
        value = 0
        for i in range(count):
            byte = self._data[self._pos >> 3]
            value |= ((byte >> (self._pos & 7)) & 1) << i
            self._pos += 1
        return value

    def dimension(self, small: bool) -> int:
        if small:
            return 8 * (1 + self.bits(5))
        return 1 + self.bits((9, 13, 18, 30)[self.bits(2)])


def _codestream(data: bytes) -> bytes | None:
    """The codestream inside a bare or ISOBMFF-boxed JPEG XL file."""
    if data.startswith(_CODESTREAM_SIGNATURE):
        return data
    if not data.startswith(_CONTAINER_SIGNATURE):
        return None
    pos = 0
    while pos + 8 <= len(data):
        size, box_type = struct.unpack_from(">I4s", data, pos)
        header = 8
        if size == 1:
            (size,) = struct.unpack_from(">Q", data, pos + 8)
            header = 16
        elif size == 0:
            size = len(data) - pos
        if box_type == b"jxlc":
            return data[pos + header : pos + size]
        if box_type == b"jxlp":
            # The first partial box starts the codestream after its index.
            return data[pos + header + 4 : pos + size]
        if size < header:
            return None
        pos += size
    return None


def jxl_size(data: bytes) -> tuple[int, int] | None:
    """Width and height a JPEG XL file declares, read without decoding pixels.

    Returns:
        None when the data holds no JPEG XL codestream.
    """
    codestream = _codestream(data)
    if codestream is None or not codestream.startswith(_CODESTREAM_SIGNATURE):
        return None
    reader = _BitReader(codestream, len(_CODESTREAM_SIGNATURE))
    small = bool(reader.bits(1))
    height = reader.dimension(small)
    ratio = reader.bits(3)
    if ratio == 0:
        return reader.dimension(small), height
    num, den = _RATIOS[ratio]
    return height * num // den, height


class GuardedJXLImageFile(JXLImageFile):
    """pillow-jxl's decoder behind a header size check and Pillow's error contract."""

    def _open(self) -> None:
        fp = self.fp
        if fp is None:
            raise SyntaxError("no JPEG XL data to read")
        start = fp.tell()
        size = jxl_size(fp.read())
        if size is None:
            raise SyntaxError("not a JPEG XL image")
        Image._decompression_bomb_check(size)
        fp.seek(start)
        try:
            super()._open()  # type: ignore[no-untyped-call]  # pillow-jxl is untyped
        except RuntimeError as exc:
            raise SyntaxError(f"broken JPEG XL image: {exc}") from exc


Image.register_open(GuardedJXLImageFile.format, GuardedJXLImageFile, _accept)
