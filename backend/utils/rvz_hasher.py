"""Native RetroAchievements hashing for GameCube/Wii RVZ and WIA disc images.

RAHasher (RALibretro/rcheevos) reads raw ``.iso``/``.gcm`` GameCube and Wii
discs, but not the block-compressed RVZ/WIA containers Dolphin creates. For
those it fails with "Not a Gamecube disc" / "Not a supported Wii file" and the
game is left without a RetroAchievements match (issues #3649 and #3650).

Neither console's RA hash depends on the whole disc. Per rcheevos:

- GameCube: ``MD5(boot/partition header incl. apploader + the up to 18
  main.dol segments referenced by the boot header)``, a few MB near the disc
  start.
- Wii: ``MD5(main header + region code + per non-update partition: the TMD
  (capped at 0x7C00) and up to 1024 encrypted 0x7C00-byte clusters)``, roughly
  32 MB per partition.

RVZ/WIA files are group-indexed, so those byte ranges can be reconstructed
with random access, decompressing only the groups a range touches, with no
subprocess and no multi-GB temporary ISO. Wii partition data is stored
decrypted and with the hash tree stripped, and RA hashes the encrypted disc
bytes, so the reconstruction recalculates the H0/H1/H2 hash tree, applies the
container's stored hash exceptions and re-encrypts the clusters with the
partition's embedded title key (AES-128-CBC). This reproduces the identical
bytes of the original disc, so the resulting hash matches RA's database (and
what Dolphin computes when playing the same file).

Format references:
- https://github.com/dolphin-emu/dolphin/blob/master/docs/WiaAndRvz.md
- https://wiibrew.org/wiki/Wii_Disc
- rcheevos ``src/rhash/hash_disc.c`` (``rc_hash_gamecube`` / ``rc_hash_wii``)
"""

import bz2
import hashlib
import lzma
import os
import struct
from typing import BinaryIO

import zstandard
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from logger.formatter import LIGHTMAGENTA
from logger.formatter import highlight as hl
from logger.logger import log

# Container extensions RAHasher can't read but which we can hash natively. The
# real container is still detected by magic; the extension only gates whether
# we attempt native hashing before falling back to RAHasher.
RVZ_NATIVE_HASH_EXTENSIONS: tuple[str, ...] = (".rvz", ".wia")

_RVZ_MAGIC = b"RVZ\x01"
_WIA_MAGIC = b"WIA\x01"

# wia_disc_t compression codes.
_COMPRESSION_NONE = 0
_COMPRESSION_PURGE = 1
_COMPRESSION_BZIP2 = 2
_COMPRESSION_LZMA = 3
_COMPRESSION_LZMA2 = 4
_COMPRESSION_ZSTD = 5

_WII_SECTOR_SIZE = 0x8000
_WII_SECTOR_DATA_SIZE = 0x7C00
_WII_SECTOR_HASH_SIZE = 0x400
_WII_SECTORS_PER_HASH_GROUP = 64

_GC_MAGIC = b"\xc2\x33\x9f\x3d"  # at disc offset 0x1C
_WII_MAGIC = b"\x5d\x1c\x9e\xa3"  # at disc offset 0x18
_GC_BASE_HEADER_SIZE = 0x2440
_MAX_GC_HEADER_SIZE = 1024 * 1024
_MAX_WII_CLUSTERS = 1024
_HASH_CHUNK_SIZE = 1024 * 1024

_PARSE_ERRORS = (
    OSError,
    ValueError,
    IndexError,
    EOFError,
    struct.error,
    lzma.LZMAError,
)


class RvzHashError(Exception):
    """Raised when an RVZ/WIA container can't be parsed for native hashing."""


class _LaggedFibonacci:
    """The PRNG GameCube/Wii discs use for junk padding (f=xor, j=32, k=521).

    RVZ stores junk ranges as a 68-byte seed plus a length; regenerating the
    stream reproduces the original disc bytes. Mirrors Dolphin's
    LaggedFibonacciGenerator, including the console's "shift by 18 instead of
    16" output quirk, which is baked into the buffer words up front.
    """

    _K = 521
    _J = 32
    _BUFFER_BYTES = _K * 4

    def __init__(self, seed: bytes) -> None:
        if len(seed) < 68:
            raise RvzHashError("truncated junk PRNG seed")
        words = list(struct.unpack(">17I", seed[:68]))
        for i in range(17, self._K):
            words.append(
                ((words[i - 17] << 23) & 0xFFFFFFFF)
                ^ (words[i - 16] >> 9)
                ^ words[i - 1]
            )
        self._words = [(w & 0xFF00FFFF) | ((w >> 2) & 0x00FF0000) for w in words]
        for _ in range(4):
            self._advance()
        self._pos = 0
        self._buffer: bytes | None = None

    def _advance(self) -> None:
        words = self._words
        for i in range(self._J):
            words[i] ^= words[i + self._K - self._J]
        for i in range(self._J, self._K):
            words[i] ^= words[i - self._J]
        self._buffer = None

    def _bytes(self) -> bytes:
        if self._buffer is None:
            self._buffer = struct.pack(f">{self._K}I", *self._words)
        return self._buffer

    def forward(self, count: int) -> None:
        self._pos += count
        while self._pos >= self._BUFFER_BYTES:
            self._advance()
            self._pos -= self._BUFFER_BYTES

    def get_bytes(self, count: int) -> bytes:
        out = bytearray()
        while count > 0:
            buffer = self._bytes()
            take = min(count, self._BUFFER_BYTES - self._pos)
            out += buffer[self._pos : self._pos + take]
            self._pos += take
            count -= take
            if self._pos == self._BUFFER_BYTES:
                self._advance()
                self._pos = 0
        return bytes(out)


def _decode_lzma_filters(lzma2: bool, compr_data: bytes) -> list[dict]:
    """Convert the 7-Zip-SDK properties stored in the header to lzma filters."""
    if lzma2:
        if len(compr_data) < 1:
            raise RvzHashError("missing LZMA2 properties")
        prop = compr_data[0]
        if prop > 40:
            raise RvzHashError("invalid LZMA2 dictionary size")
        dict_size = 0xFFFFFFFF if prop == 40 else (2 | (prop & 1)) << (prop // 2 + 11)
        return [{"id": lzma.FILTER_LZMA2, "dict_size": max(dict_size, 1 << 12)}]

    if len(compr_data) < 5:
        raise RvzHashError("missing LZMA properties")
    d = compr_data[0]
    if d >= 9 * 5 * 5:
        raise RvzHashError("invalid LZMA properties")
    lc = d % 9
    d //= 9
    pb = d // 5
    lp = d % 5
    dict_size = struct.unpack_from("<I", compr_data, 1)[0]
    return [
        {
            "id": lzma.FILTER_LZMA1,
            "dict_size": max(dict_size, 1 << 12),
            "lc": lc,
            "lp": lp,
            "pb": pb,
        }
    ]


class _WiiPartition:
    """A wia_part_t entry: title key plus up to two group-backed data ranges."""

    __slots__ = ("key", "segments", "base_sector")

    def __init__(self, key: bytes, segments: list[tuple[int, int, int, int]]) -> None:
        self.key = key
        # (first_sector, n_sectors, group_index, n_groups), empty ones dropped
        self.segments = [seg for seg in segments if seg[1] > 0]
        if not self.segments:
            raise RvzHashError("Wii partition without data segments")
        self.base_sector = min(seg[0] for seg in self.segments)


class _RvzReader:
    """Random access over the reconstructed disc bytes of an RVZ/WIA image.

    ``read_at`` serves any byte range of the original disc: non-partition
    ranges come from the raw-data groups, Wii partition data is rebuilt into
    its encrypted on-disc form (hash tree + hash exceptions + AES-128-CBC),
    and unmapped ranges read as zeroes.
    """

    def __init__(self, fh: BinaryIO) -> None:
        self._fh = fh
        header_1 = fh.read(0x48)
        if len(header_1) < 0x48:
            raise RvzHashError("truncated file header")
        magic = header_1[:4]
        if magic not in (_RVZ_MAGIC, _WIA_MAGIC):
            raise RvzHashError(f"unrecognized container magic {magic[:4]!r}")
        self.is_rvz = magic == _RVZ_MAGIC

        header_2_size = struct.unpack_from(">I", header_1, 0x0C)[0]
        self.iso_size = struct.unpack_from(">Q", header_1, 0x24)[0]
        if not 0xDC <= header_2_size <= 0x400:
            raise RvzHashError("invalid disc header size")
        header_2 = fh.read(header_2_size)
        if len(header_2) < 0xDC:
            raise RvzHashError("truncated disc header")

        self.disc_type, self.compression, _level, self.chunk_size = struct.unpack_from(
            ">IIiI", header_2, 0
        )
        if self.compression == _COMPRESSION_PURGE:
            raise RvzHashError("PURGE compression is not supported")
        if self.compression not in (
            _COMPRESSION_NONE,
            _COMPRESSION_BZIP2,
            _COMPRESSION_LZMA,
            _COMPRESSION_LZMA2,
            _COMPRESSION_ZSTD,
        ):
            raise RvzHashError(f"unknown compression method {self.compression}")
        if self.chunk_size == 0 or self.chunk_size % _WII_SECTOR_SIZE:
            raise RvzHashError("invalid chunk size")

        self.disc_header = header_2[0x10:0x90]
        n_part, part_t_size = struct.unpack_from(">II", header_2, 0x90)
        part_off = struct.unpack_from(">Q", header_2, 0x98)[0]
        n_raw, raw_off, raw_size = struct.unpack_from(">IQI", header_2, 0xB4)
        n_groups, group_off, group_size = struct.unpack_from(">IQI", header_2, 0xC4)
        compr_data_len = header_2[0xD4]
        self._compr_data = header_2[0xD5 : 0xD5 + min(compr_data_len, 7)]

        if n_part > 0x100 or n_raw > 0x10000 or n_groups > 0x1000000:
            raise RvzHashError("implausible entry counts")

        # Partition entries are stored uncompressed. Entries smaller than
        # 0x30 bytes are zero-padded per the spec.
        self.partitions: list[_WiiPartition] = []
        if n_part:
            if part_t_size > 0x400:
                raise RvzHashError("invalid partition entry size")
            fh.seek(part_off)
            blob = fh.read(n_part * part_t_size)
            if len(blob) < n_part * part_t_size:
                raise RvzHashError("truncated partition entries")
            for i in range(n_part):
                entry = blob[i * part_t_size : (i + 1) * part_t_size].ljust(
                    0x30, b"\x00"
                )
                segments = [
                    struct.unpack_from(">IIII", entry, base) for base in (0x10, 0x20)
                ]
                self.partitions.append(_WiiPartition(entry[:16], segments))

        # Raw-data and group entry tables are stored compressed.
        raw_blob = self._decompress_blob(raw_off, raw_size, n_raw * 0x18)
        self._raw_entries: list[tuple[int, int, int, int]] = []
        for i in range(n_raw):
            data_off, data_size, group_index, entry_groups = struct.unpack_from(
                ">QQII", raw_blob, i * 0x18
            )
            # The first entry claims to start at 0x80; align entries down to a
            # sector boundary (the group data actually covers from there).
            skew = data_off % _WII_SECTOR_SIZE
            self._raw_entries.append(
                (data_off - skew, data_size + skew, group_index, entry_groups)
            )

        entry_size = 0x0C if self.is_rvz else 0x08
        group_blob = self._decompress_blob(group_off, group_size, n_groups * entry_size)
        self._groups: list[tuple[int, int, int]] = []
        for i in range(n_groups):
            if self.is_rvz:
                self._groups.append(
                    struct.unpack_from(">III", group_blob, i * entry_size)
                )
            else:
                off4, size_field = struct.unpack_from(">II", group_blob, i * entry_size)
                self._groups.append((off4, size_field, 0))

        # Per-group hash-exception lists for Wii partition data. One list per
        # 2 MiB of chunk, or a single list for RVZ chunks below 2 MiB.
        self._except_lists_per_group = max(1, self.chunk_size // 0x200000)
        self._sectors_per_chunk = self.chunk_size // _WII_SECTOR_SIZE
        self._chunk_data_size = self._sectors_per_chunk * _WII_SECTOR_DATA_SIZE

        self._group_cache: dict[int, tuple[bytes, list[tuple[int, int, bytes]]]] = {}
        self._hash_group_cache: dict[tuple[int, int], bytes] = {}

    def close(self) -> None:
        try:
            self._fh.close()
        except OSError:
            pass

    # -- container plumbing -------------------------------------------------

    def _decompress(self, blob: bytes) -> bytes:
        if self.compression == _COMPRESSION_NONE:
            return blob
        if self.compression == _COMPRESSION_BZIP2:
            return bz2.decompress(blob)
        if self.compression in (_COMPRESSION_LZMA, _COMPRESSION_LZMA2):
            filters = _decode_lzma_filters(
                self.compression == _COMPRESSION_LZMA2, self._compr_data
            )
            return lzma.LZMADecompressor(
                format=lzma.FORMAT_RAW, filters=filters
            ).decompress(blob)
        return zstandard.ZstdDecompressor().decompressobj().decompress(blob)

    def _decompress_blob(self, offset: int, size: int, expected: int) -> bytes:
        self._fh.seek(offset)
        blob = self._fh.read(size)
        if len(blob) < size:
            raise RvzHashError("truncated entry table")
        out = self._decompress(blob)
        if len(out) < expected:
            raise RvzHashError("entry table shorter than expected")
        return out

    def _unpack_rvz(self, packed: bytes, data_offset: int, expected: int) -> bytes:
        """Decode RVZ packing: literal runs plus PRNG-generated junk runs."""
        out = bytearray()
        pos = 0
        while pos + 4 <= len(packed) and len(out) < expected:
            size = struct.unpack_from(">I", packed, pos)[0]
            pos += 4
            if size & 0x80000000:
                size &= 0x7FFFFFFF
                lfg = _LaggedFibonacci(packed[pos : pos + 68])
                pos += 68
                lfg.forward((data_offset + len(out)) % _WII_SECTOR_SIZE)
                out += lfg.get_bytes(min(size, expected - len(out)))
            else:
                out += packed[pos : pos + size]
                pos += size
        return bytes(out)

    def _parse_exception_lists(
        self, stream: bytes, align: bool
    ) -> tuple[list[tuple[int, int, bytes]], int]:
        """Parse the group's wia_except_list_t structs.

        Returns (exceptions, bytes consumed); each exception is
        (sector offset within the group, offset in that sector's hash area,
        20-byte replacement digest).
        """
        exceptions: list[tuple[int, int, bytes]] = []
        pos = 0
        for list_ix in range(self._except_lists_per_group):
            if pos + 2 > len(stream):
                raise RvzHashError("truncated hash exception list")
            (count,) = struct.unpack_from(">H", stream, pos)
            pos += 2
            if count > 3328:
                raise RvzHashError("implausible hash exception count")
            for _ in range(count):
                if pos + 22 > len(stream):
                    raise RvzHashError("truncated hash exception entry")
                (offset,) = struct.unpack_from(">H", stream, pos)
                sector = list_ix * 64 + offset // _WII_SECTOR_HASH_SIZE
                exceptions.append(
                    (
                        sector,
                        offset % _WII_SECTOR_HASH_SIZE,
                        stream[pos + 2 : pos + 22],
                    )
                )
                pos += 22
        if align:
            pos += (-pos) % 4
        return exceptions, pos

    def _decode_group(
        self, index: int, expected: int, data_offset: int, with_exceptions: bool
    ) -> tuple[bytes, list[tuple[int, int, bytes]]]:
        """Decode one group into (data, hash exceptions), zero-padded/cached."""
        cached = self._group_cache.get(index)
        if cached is not None:
            return cached

        if index >= len(self._groups):
            raise RvzHashError("group index out of range")
        data_off4, size_field, packed_size = self._groups[index]
        if self.is_rvz:
            compressed = bool(size_field & 0x80000000)
            stored_size = size_field & 0x7FFFFFFF
        else:
            compressed = self.compression != _COMPRESSION_NONE
            stored_size = size_field

        result: tuple[bytes, list[tuple[int, int, bytes]]]
        if stored_size == 0:
            result = (b"\x00" * expected, [])
        else:
            self._fh.seek(data_off4 << 2)
            blob = self._fh.read(stored_size)
            if len(blob) < stored_size:
                raise RvzHashError("truncated group data")

            stream = self._decompress(blob) if compressed else blob
            exceptions: list[tuple[int, int, bytes]] = []
            if with_exceptions:
                # Uncompressed exception lists are padded to a 4-byte
                # boundary; compressed ones are not.
                exceptions, consumed = self._parse_exception_lists(
                    stream, align=not compressed
                )
                stream = stream[consumed:]

            if self.is_rvz and packed_size:
                data = self._unpack_rvz(stream[:packed_size], data_offset, expected)
            else:
                data = stream[:expected]
            if len(data) < expected:
                data = data + b"\x00" * (expected - len(data))
            result = (data, exceptions)

        if len(self._group_cache) >= 16:
            self._group_cache.clear()
        self._group_cache[index] = result
        return result

    # -- raw (non-partition) data -------------------------------------------

    def _read_raw_into(self, out: bytearray, offset: int, length: int) -> None:
        end = offset + length
        for entry_start, entry_size, group_index, entry_groups in self._raw_entries:
            entry_end = entry_start + entry_size
            lo = max(offset, entry_start)
            hi = min(end, entry_end)
            while lo < hi:
                g = (lo - entry_start) // self.chunk_size
                if g >= entry_groups:
                    break
                group_start = entry_start + g * self.chunk_size
                expected = min(self.chunk_size, entry_end - group_start)
                data, _ = self._decode_group(
                    group_index + g, expected, g * self.chunk_size, False
                )
                skip = lo - group_start
                take = min(hi - lo, expected - skip)
                if take <= 0:
                    break
                out[lo - offset : lo - offset + take] = data[skip : skip + take]
                lo += take

    # -- Wii partition data --------------------------------------------------

    def _read_partition_decrypted(
        self, partition: _WiiPartition, offset: int, length: int
    ) -> bytes:
        """Read the decrypted, hashless partition data address space."""
        out = bytearray(length)
        end = offset + length
        for first_sector, n_sectors, group_index, seg_groups in partition.segments:
            seg_start = (first_sector - partition.base_sector) * _WII_SECTOR_DATA_SIZE
            seg_size = n_sectors * _WII_SECTOR_DATA_SIZE
            seg_end = seg_start + seg_size
            lo = max(offset, seg_start)
            hi = min(end, seg_end)
            while lo < hi:
                g = (lo - seg_start) // self._chunk_data_size
                if g >= seg_groups:
                    break
                group_start = seg_start + g * self._chunk_data_size
                expected = min(self._chunk_data_size, seg_end - group_start)
                data, _ = self._decode_group(
                    group_index + g, expected, g * self._chunk_data_size, True
                )
                skip = lo - group_start
                take = min(hi - lo, expected - skip)
                if take <= 0:
                    break
                out[lo - offset : lo - offset + take] = data[skip : skip + take]
                lo += take
        return bytes(out)

    def _partition_exceptions(
        self, partition: _WiiPartition, sector_lo: int, sector_hi: int
    ) -> list[tuple[int, int, bytes]]:
        """Hash exceptions for partition-relative sectors [lo, hi)."""
        exceptions: list[tuple[int, int, bytes]] = []
        for first_sector, n_sectors, group_index, seg_groups in partition.segments:
            seg_sector_base = first_sector - partition.base_sector
            seg_size = n_sectors * _WII_SECTOR_DATA_SIZE
            for g in range(seg_groups):
                group_sector = seg_sector_base + g * self._sectors_per_chunk
                if group_sector >= sector_hi:
                    break
                if group_sector + self._sectors_per_chunk <= sector_lo:
                    continue
                expected = min(
                    self._chunk_data_size, seg_size - g * self._chunk_data_size
                )
                _, group_exceptions = self._decode_group(
                    group_index + g, expected, g * self._chunk_data_size, True
                )
                for sector_in_group, hash_offset, digest in group_exceptions:
                    sector = group_sector + sector_in_group
                    if sector_lo <= sector < sector_hi:
                        exceptions.append((sector, hash_offset, digest))
        return exceptions

    def _encrypted_hash_group(self, partition_index: int, hash_group: int) -> bytes:
        """Rebuild one 64-sector hash group (2 MiB) of encrypted disc bytes."""
        cache_key = (partition_index, hash_group)
        cached = self._hash_group_cache.get(cache_key)
        if cached is not None:
            return cached

        partition = self.partitions[partition_index]
        sector_lo = hash_group * _WII_SECTORS_PER_HASH_GROUP
        blocks = [
            self._read_partition_decrypted(
                partition,
                (sector_lo + b) * _WII_SECTOR_DATA_SIZE,
                _WII_SECTOR_DATA_SIZE,
            )
            for b in range(_WII_SECTORS_PER_HASH_GROUP)
        ]

        # H0: 31 SHA-1 digests per sector, one per 0x400 bytes of data.
        h0_tables = [
            b"".join(
                hashlib.sha1(
                    block[j * 0x400 : (j + 1) * 0x400], usedforsecurity=False
                ).digest()
                for j in range(31)
            )
            for block in blocks
        ]
        # H1: per 8-sector subgroup, the SHA-1 of each member's H0 table.
        h1_tables = [
            b"".join(
                hashlib.sha1(h0_tables[sub * 8 + k], usedforsecurity=False).digest()
                for k in range(8)
            )
            for sub in range(8)
        ]
        # H2: the SHA-1 of each subgroup's H1 table, shared by all 64 sectors.
        h2_table = b"".join(
            hashlib.sha1(h1_tables[sub], usedforsecurity=False).digest()
            for sub in range(8)
        )

        headers = []
        for b in range(_WII_SECTORS_PER_HASH_GROUP):
            header = bytearray(_WII_SECTOR_HASH_SIZE)
            header[0x000:0x26C] = h0_tables[b]
            header[0x280:0x320] = h1_tables[b // 8]
            header[0x340:0x3E0] = h2_table
            headers.append(header)

        for sector, hash_offset, digest in self._partition_exceptions(
            partition, sector_lo, sector_lo + _WII_SECTORS_PER_HASH_GROUP
        ):
            local = headers[sector - sector_lo]
            local[hash_offset : hash_offset + len(digest)] = digest[
                : _WII_SECTOR_HASH_SIZE - hash_offset
            ]

        out = bytearray()
        for b in range(_WII_SECTORS_PER_HASH_GROUP):
            hash_cipher = Cipher(
                algorithms.AES(partition.key), modes.CBC(b"\x00" * 16)
            ).encryptor()
            enc_header = hash_cipher.update(bytes(headers[b])) + hash_cipher.finalize()
            # The data IV is the encrypted hash area's bytes at 0x3D0.
            data_cipher = Cipher(
                algorithms.AES(partition.key), modes.CBC(enc_header[0x3D0:0x3E0])
            ).encryptor()
            out += enc_header + data_cipher.update(blocks[b]) + data_cipher.finalize()

        if len(self._hash_group_cache) >= 2:
            self._hash_group_cache.clear()
        self._hash_group_cache[cache_key] = bytes(out)
        return bytes(out)

    def _read_partition_encrypted_into(
        self, out: bytearray, offset: int, length: int, partition_index: int
    ) -> None:
        partition = self.partitions[partition_index]
        end = offset + length
        group_bytes = _WII_SECTORS_PER_HASH_GROUP * _WII_SECTOR_SIZE
        for first_sector, n_sectors, _, _ in partition.segments:
            seg_start = first_sector * _WII_SECTOR_SIZE
            seg_end = seg_start + n_sectors * _WII_SECTOR_SIZE
            lo = max(offset, seg_start)
            hi = min(end, seg_end)
            data_start = partition.base_sector * _WII_SECTOR_SIZE
            while lo < hi:
                hash_group = (lo - data_start) // group_bytes
                group_start = data_start + hash_group * group_bytes
                data = self._encrypted_hash_group(partition_index, hash_group)
                skip = lo - group_start
                take = min(hi - lo, group_bytes - skip)
                out[lo - offset : lo - offset + take] = data[skip : skip + take]
                lo += take

    # -- public API -----------------------------------------------------------

    def read_at(self, offset: int, length: int) -> bytes:
        """Reconstructed disc bytes at [offset, offset+length), zero-filled."""
        out = bytearray(length)
        self._read_raw_into(out, offset, length)
        for i in range(len(self.partitions)):
            self._read_partition_encrypted_into(out, offset, length, i)
        if offset < 0x80:
            take = min(0x80 - offset, length)
            out[0:take] = self.disc_header[offset : offset + take]
        return bytes(out)


def _open_reader(file_path: str) -> _RvzReader:
    fh = open(file_path, "rb")  # noqa: SIM115 - ownership passes to the reader
    try:
        return _RvzReader(fh)
    except BaseException:
        fh.close()
        raise


def _be32(data: bytes, offset: int = 0) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def _hash_chunked(md5, reader: _RvzReader, offset: int, size: int) -> None:
    """Feed [offset, offset+size) to the hash in bounded chunks."""
    pos = offset
    remaining = size
    while remaining > 0:
        take = min(remaining, _HASH_CHUNK_SIZE)
        md5.update(reader.read_at(pos, take))
        pos += take
        remaining -= take


def _hash_nintendo_disc_partition(
    md5, reader: _RvzReader, part_offset: int, wii_shift: int
) -> None:
    """Mirror of rcheevos rc_hash_nintendo_disc_partition."""
    body, trailer = struct.unpack(
        ">II", reader.read_at(part_offset + _GC_BASE_HEADER_SIZE + 0x14, 8)
    )
    header_size = min(_GC_BASE_HEADER_SIZE + 0x20 + body + trailer, _MAX_GC_HEADER_SIZE)
    _hash_chunked(md5, reader, part_offset, header_size)

    dol_offset = _be32(reader.read_at(part_offset + 0x420, 4)) << wii_shift
    dol_header = reader.read_at(part_offset + dol_offset, 0xD8)
    for ix in range(18):
        seg_offset = _be32(dol_header, ix * 4) << wii_shift
        seg_size = _be32(dol_header, 0x90 + ix * 4) << wii_shift
        if seg_size:
            # rcheevos seeks these relative to the partition, not the DOL.
            _hash_chunked(md5, reader, part_offset + seg_offset, seg_size)


def calculate_gamecube_ra_hash(file_path: str) -> str:
    """Compute the RetroAchievements GameCube hash from an RVZ/WIA image.

    Returns the 32-char MD5 hex digest, or an empty string if the container
    can't be parsed or doesn't hold a GameCube disc (the caller then falls
    back to RAHasher).
    """
    try:
        reader = _open_reader(file_path)
    except (OSError, RvzHashError) as exc:
        log.warning(
            f"Could not open RVZ/WIA container {hl(file_path)} for native "
            f"{hl('RA', color=LIGHTMAGENTA)} hashing: {exc}"
        )
        return ""

    try:
        if reader.read_at(0x1C, 4) != _GC_MAGIC:
            log.warning(
                f"{hl(file_path)} does not hold a GameCube disc; can't compute "
                f"native {hl('RA', color=LIGHTMAGENTA)} hash"
            )
            return ""
        md5 = hashlib.md5(usedforsecurity=False)
        _hash_nintendo_disc_partition(md5, reader, 0, 0)
        return md5.hexdigest()
    except (RvzHashError, *_PARSE_ERRORS) as exc:
        log.warning(
            f"Failed to read GameCube disc data from {hl(file_path)} for native "
            f"{hl('RA', color=LIGHTMAGENTA)} hashing: {exc}"
        )
        return ""
    finally:
        reader.close()


def _hash_wii_disc(md5, reader: _RvzReader) -> None:
    """Mirror of rcheevos rc_hash_wii_disc for encrypted retail discs."""
    if reader.read_at(0x61, 1) != b"\x00":
        raise RvzHashError("decrypted Wii disc images are not supported")

    md5.update(reader.read_at(0, 0x80))
    md5.update(reader.read_at(0x4E000, 4))

    info = struct.unpack(">8I", reader.read_at(0x40000, 32))
    partitions: list[tuple[int, int]] = []
    for j in range(0, 8, 2):
        count, table_off4 = info[j], info[j + 1]
        if count > 0x100:
            raise RvzHashError("implausible partition count")
        for i in range(count):
            entry = reader.read_at((table_off4 << 2) + i * 8, 8)
            partitions.append(struct.unpack(">II", entry))
    if not partitions:
        raise RvzHashError("no partitions found")

    for part_off4, part_type in partitions:
        if part_type == 1:  # update partition
            continue
        part_start = part_off4 << 2

        tmd_size, tmd_off4 = struct.unpack(">II", reader.read_at(part_start + 0x2A4, 8))
        tmd_size = min(tmd_size, _WII_SECTOR_DATA_SIZE)
        md5.update(reader.read_at(part_start + (tmd_off4 << 2), tmd_size))

        data_off4, data_size4 = struct.unpack(
            ">II", reader.read_at(part_start + 0x2B8, 8)
        )
        # rcheevos reads the partition-relative data offset field and then
        # seeks with it as an absolute file offset; mirror that exactly.
        part_offset = data_off4 << 2
        part_size = data_size4 << 2

        clusters = min(part_size // _WII_SECTOR_SIZE, _MAX_WII_CLUSTERS)
        for ix in range(clusters):
            md5.update(
                reader.read_at(
                    part_offset + ix * _WII_SECTOR_SIZE + _WII_SECTOR_HASH_SIZE,
                    _WII_SECTOR_DATA_SIZE,
                )
            )


def calculate_wii_ra_hash(file_path: str) -> str:
    """Compute the RetroAchievements Wii hash from an RVZ/WIA image.

    Returns the 32-char MD5 hex digest, or an empty string if the container
    can't be parsed or doesn't hold an encrypted Wii disc (the caller then
    falls back to RAHasher).
    """
    try:
        reader = _open_reader(file_path)
    except (OSError, RvzHashError) as exc:
        log.warning(
            f"Could not open RVZ/WIA container {hl(file_path)} for native "
            f"{hl('RA', color=LIGHTMAGENTA)} hashing: {exc}"
        )
        return ""

    try:
        if reader.read_at(0x18, 4) != _WII_MAGIC:
            log.warning(
                f"{hl(file_path)} does not hold a Wii disc; can't compute "
                f"native {hl('RA', color=LIGHTMAGENTA)} hash"
            )
            return ""
        md5 = hashlib.md5(usedforsecurity=False)
        _hash_wii_disc(md5, reader)
        return md5.hexdigest()
    except (RvzHashError, *_PARSE_ERRORS) as exc:
        log.warning(
            f"Failed to read Wii disc data from {hl(file_path)} for native "
            f"{hl('RA', color=LIGHTMAGENTA)} hashing: {exc}"
        )
        return ""
    finally:
        reader.close()


def is_rvz_native_hash_file(file_path: str) -> bool:
    """Whether ``file_path`` is an RVZ/WIA image we hash natively (by extension)."""
    return os.path.splitext(file_path)[1].lower() in RVZ_NATIVE_HASH_EXTENSIONS
