"""Native RetroAchievements hashing for PSP compressed-ISO containers.

RAHasher (RALibretro/rcheevos) reads raw ``.iso``, ``.bin``/``.cue`` and
``.chd`` PSP discs, but not the block-compressed ISO containers PPSSPP uses
(``.cso``/``.ciso``/``.zso``/``.dax``). For those it fails with "Could not open
track" and the game is left without a RetroAchievements match.

The PSP RA hash does not depend on the whole disc. rcheevos computes it as
``MD5(PSP_GAME/PARAM.SFO contents + PSP_GAME/SYSDIR/EBOOT.BIN contents)``, each
file capped at 64 MiB. Those two files are only a few MB, and the compressed
containers are block-indexed, so we can decompress just the handful of blocks
they occupy and hash them in-process, with no subprocess and no multi-GB
temporary ISO. This produces the identical hash RA stores (and PPSSPP computes),
so the game matches.
"""

import hashlib
import os
import struct
import zlib
from typing import BinaryIO

from logger.formatter import LIGHTMAGENTA
from logger.formatter import highlight as hl
from logger.logger import log
from utils.iso9660 import Iso9660

# Container extensions RAHasher can't read but which we can hash natively. The
# real container is still detected by magic; the extension only gates whether we
# attempt native hashing before falling back to RAHasher.
PSP_NATIVE_HASH_EXTENSIONS: tuple[str, ...] = (".cso", ".ciso", ".zso", ".dax")

# Files that make up the PSP RA hash, in order, relative to the ISO root.
_PARAM_SFO_PATH = "PSP_GAME/PARAM.SFO"
_EBOOT_BIN_PATH = "PSP_GAME/SYSDIR/EBOOT.BIN"

# rcheevos caps each hashed file at MAX_BUFFER_SIZE (64 MiB). We mirror that so
# our hash matches RA's database byte-for-byte even for oversized EBOOT.BIN.
_MAX_HASH_BYTES = 64 * 1024 * 1024

# Top bit of a CISO/ZISO index entry marks an uncompressed (plain) block.
_CISO_PLAIN_FLAG = 0x80000000
_CISO_POSITION_MASK = 0x7FFFFFFF


class PspHashError(Exception):
    """Raised when a PSP container can't be parsed for native RA hashing."""


def _inflate(raw: bytes) -> bytes:
    """Inflate a deflate stream, tolerating both raw and zlib/gzip-wrapped data.

    CISO writers disagree on whether blocks carry a zlib header (maxcso emits
    raw deflate; the classic ``ciso`` tool emits a full zlib stream), so try
    raw first and fall back to header auto-detection.
    """
    try:
        return zlib.decompress(raw, -zlib.MAX_WBITS)
    except zlib.error:
        return zlib.decompress(raw, zlib.MAX_WBITS | 32)


def _lz4_decompress_block(src: bytes, max_size: int) -> bytes:
    """Decompress a single raw LZ4 block (no frame header), as used by ZISO."""
    out = bytearray()
    i, n = 0, len(src)
    while i < n:
        token = src[i]
        i += 1

        literal_len = token >> 4
        if literal_len == 15:
            while i < n:
                b = src[i]
                i += 1
                literal_len += b
                if b != 0xFF:
                    break
        out += src[i : i + literal_len]
        i += literal_len
        if i >= n:
            break  # trailing literals: end of block

        offset = src[i] | (src[i + 1] << 8)
        i += 2
        if offset == 0 or offset > len(out):
            break

        match_len = (token & 0x0F) + 4
        if (token & 0x0F) == 15:
            while i < n:
                b = src[i]
                i += 1
                match_len += b
                if b != 0xFF:
                    break

        start = len(out) - offset
        for _ in range(match_len):
            out.append(out[start])
            start += 1
        if len(out) >= max_size:
            break

    return bytes(out[:max_size])


class _BlockDiscImage:
    """Random-access view over a block-indexed compressed disc image.

    Subclasses describe how to locate and decode a single block; this base
    turns ``read_at`` byte ranges into the right block reads, decoding only the
    blocks a range touches and caching the most recent few.
    """

    def __init__(self, fh: BinaryIO, size: int, block_size: int) -> None:
        self._fh = fh
        self.size = size
        self._block_size = block_size
        self._cache: dict[int, bytes] = {}

    def _decode_block(self, index: int) -> bytes:  # pragma: no cover - abstract
        raise NotImplementedError

    def _block(self, index: int) -> bytes:
        cached = self._cache.get(index)
        if cached is not None:
            return cached
        block = self._decode_block(index)
        if len(self._cache) >= 4:
            self._cache.clear()
        self._cache[index] = block
        return block

    def read_at(self, offset: int, length: int) -> bytes:
        out = bytearray()
        end = min(offset + length, self.size)
        pos = offset
        while pos < end:
            block = self._block(pos // self._block_size)
            start = pos % self._block_size
            take = min(len(block) - start, end - pos)
            if take <= 0:
                break
            out += block[start : start + take]
            pos += take
        return bytes(out)

    def close(self) -> None:
        try:
            self._fh.close()
        except OSError:
            pass


class _CisoDiscImage(_BlockDiscImage):
    """CISO (``.cso``/``.ciso``) and ZISO (``.zso``) block container.

    Both share the same header and index layout; ZISO blocks are LZ4-compressed
    while CISO blocks are deflate-compressed.
    """

    def __init__(self, fh: BinaryIO) -> None:
        header = fh.read(24)
        if len(header) < 24:
            raise PspHashError("truncated CISO/ZISO header")

        magic = header[:4]
        total_bytes = struct.unpack_from("<Q", header, 8)[0]
        block_size = struct.unpack_from("<I", header, 16)[0]
        align = header[21]
        if block_size == 0:
            raise PspHashError("invalid CISO/ZISO block size")

        num_blocks = (total_bytes + block_size - 1) // block_size
        index_raw = fh.read((num_blocks + 1) * 4)
        if len(index_raw) < (num_blocks + 1) * 4:
            raise PspHashError("truncated CISO/ZISO index table")

        self._index = struct.unpack(f"<{num_blocks + 1}I", index_raw)
        self._align = align
        self._lz4 = magic == b"ZISO"
        super().__init__(fh, total_bytes, block_size)

    def _decode_block(self, index: int) -> bytes:
        entry = self._index[index]
        nxt = self._index[index + 1]
        pos = (entry & _CISO_POSITION_MASK) << self._align
        next_pos = (nxt & _CISO_POSITION_MASK) << self._align

        self._fh.seek(pos)
        raw = self._fh.read(next_pos - pos)
        if entry & _CISO_PLAIN_FLAG:
            return raw[: self._block_size]
        if self._lz4:
            return _lz4_decompress_block(raw, self._block_size)
        return _inflate(raw)


class _DaxDiscImage(_BlockDiscImage):
    """DAX (``.dax``) block container: fixed 8 KiB blocks, deflate-compressed,
    with an optional table of non-compressed (raw) block ranges."""

    _DAX_BLOCK_SIZE = 0x2000

    def __init__(self, fh: BinaryIO) -> None:
        header = fh.read(32)
        if len(header) < 16:
            raise PspHashError("truncated DAX header")

        uncompressed_size = struct.unpack_from("<I", header, 4)[0]
        version = struct.unpack_from("<I", header, 8)[0]
        nc_areas = struct.unpack_from("<I", header, 12)[0]

        num_blocks = (
            uncompressed_size + self._DAX_BLOCK_SIZE - 1
        ) // self._DAX_BLOCK_SIZE
        offsets_raw = fh.read(num_blocks * 4)
        sizes_raw = fh.read(num_blocks * 2)
        if len(offsets_raw) < num_blocks * 4 or len(sizes_raw) < num_blocks * 2:
            raise PspHashError("truncated DAX block tables")

        self._offsets = struct.unpack(f"<{num_blocks}I", offsets_raw)
        self._sizes = struct.unpack(f"<{num_blocks}H", sizes_raw)

        self._plain_blocks: set[int] = set()
        if version >= 1 and nc_areas:
            nc_raw = fh.read(nc_areas * 8)
            for k in range(0, len(nc_raw) - 7, 8):
                start, count = struct.unpack_from("<II", nc_raw, k)
                self._plain_blocks.update(range(start, start + count))

        super().__init__(fh, uncompressed_size, self._DAX_BLOCK_SIZE)

    def _decode_block(self, index: int) -> bytes:
        self._fh.seek(self._offsets[index])
        raw = self._fh.read(self._sizes[index])
        if index in self._plain_blocks:
            return raw[: self._block_size]
        return _inflate(raw)


def _open_disc_image(file_path: str) -> _BlockDiscImage:
    """Open a PSP compressed-ISO container, dispatching on its magic bytes."""
    fh = open(file_path, "rb")  # noqa: SIM115 - ownership passes to the image
    try:
        magic = fh.read(4)
        fh.seek(0)
        if magic in (b"CISO", b"ZISO"):
            return _CisoDiscImage(fh)
        if magic == b"DAX\x00":
            return _DaxDiscImage(fh)
        raise PspHashError(f"unrecognized PSP container magic {magic!r}")
    except BaseException:
        fh.close()
        raise


def calculate_psp_ra_hash(file_path: str) -> str:
    """Compute the RetroAchievements PSP hash from a compressed-ISO container.

    Returns the 32-char MD5 hex digest, or an empty string if the container
    can't be parsed or doesn't hold the expected PSP files (the caller then
    falls back to RAHasher).
    """
    try:
        image = _open_disc_image(file_path)
    except (OSError, PspHashError) as exc:
        log.warning(
            f"Could not open PSP container {hl(file_path)} for native "
            f"{hl('RA', color=LIGHTMAGENTA)} hashing: {exc}"
        )
        return ""

    try:
        iso = Iso9660(image)
        param_sfo = iso.read_file(_PARAM_SFO_PATH, _MAX_HASH_BYTES)
        eboot_bin = iso.read_file(_EBOOT_BIN_PATH, _MAX_HASH_BYTES)
    except (
        OSError,
        PspHashError,
        struct.error,
        zlib.error,
        ValueError,
        IndexError,
    ) as exc:
        log.warning(
            f"Failed to read PSP files from {hl(file_path)} for native "
            f"{hl('RA', color=LIGHTMAGENTA)} hashing: {exc}"
        )
        return ""
    finally:
        image.close()

    if param_sfo is None or eboot_bin is None:
        log.warning(
            f"PSP container {hl(file_path)} is missing PARAM.SFO or EBOOT.BIN; "
            f"can't compute native {hl('RA', color=LIGHTMAGENTA)} hash"
        )
        return ""

    md5 = hashlib.md5(usedforsecurity=False)
    md5.update(param_sfo)
    md5.update(eboot_bin)
    return md5.hexdigest()


def is_psp_native_hash_file(file_path: str) -> bool:
    """Whether ``file_path`` is a PSP container we hash natively (by extension)."""
    return os.path.splitext(file_path)[1].lower() in PSP_NATIVE_HASH_EXTENSIONS
