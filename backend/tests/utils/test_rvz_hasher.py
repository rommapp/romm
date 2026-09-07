import bz2
import hashlib
import lzma
import struct
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import zstandard
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from utils.rvz_hasher import (
    RVZ_NATIVE_HASH_EXTENSIONS,
    _LaggedFibonacci,
    calculate_gamecube_ra_hash,
    calculate_wii_ra_hash,
    is_rvz_native_hash_file,
)

WII_SECTOR_SIZE = 0x8000
WII_SECTOR_DATA_SIZE = 0x7C00
WII_SECTOR_HASH_SIZE = 0x400

# wia_disc_t compression codes.
COMPRESSION_NONE = 0
COMPRESSION_BZIP2 = 2
COMPRESSION_LZMA = 3
COMPRESSION_LZMA2 = 4
COMPRESSION_ZSTD = 5

# Fixed LZMA parameters used by the builder (and mirrored by the reader via
# the compr_data bytes in the header).
_LZMA1_FILTERS = [
    {"id": lzma.FILTER_LZMA1, "dict_size": 1 << 16, "lc": 3, "lp": 0, "pb": 2}
]
_LZMA1_COMPR_DATA = bytes([(2 * 5 + 0) * 9 + 3]) + struct.pack("<I", 1 << 16)
_LZMA2_FILTERS = [{"id": lzma.FILTER_LZMA2, "dict_size": 1 << 20}]
_LZMA2_COMPR_DATA = bytes([18])  # (2 | 0) << (18 // 2 + 11) == 1 MiB


# ---------------------------------------------------------------------------
# Reference implementations, written from the specs (rcheevos hash_disc.c and
# Dolphin's WiaAndRvz.md / wiibrew Wii disc docs) independently of the
# production reader so the two meet only at the format boundary.
# ---------------------------------------------------------------------------


class SpecLfg:
    """Lagged Fibonacci PRNG as described in Dolphin's WiaAndRvz.md spec."""

    def __init__(self, seed: bytes) -> None:
        words = list(struct.unpack(">17I", seed))
        for i in range(17, 521):
            words.append(
                (((words[i - 17] << 23) & 0xFFFFFFFF) ^ (words[i - 16] >> 9))
                ^ words[i - 1]
            )
        self._buf = words
        for _ in range(4):
            self._advance()
        self._pos = 0

    def _advance(self) -> None:
        buf = self._buf
        for i in range(32):
            buf[i] ^= buf[i + 521 - 32]
        for i in range(32, 521):
            buf[i] ^= buf[i - 32]

    def forward(self, count: int) -> None:
        self._pos += count
        while self._pos >= 521 * 4:
            self._advance()
            self._pos -= 521 * 4

    def get_bytes(self, count: int) -> bytes:
        out = bytearray()
        while count > 0:
            word = self._buf[self._pos // 4]
            # The spec's output code shifts the second byte by 18, not 16.
            quad = bytes(
                [
                    (word >> 24) & 0xFF,
                    (word >> 18) & 0xFF,
                    (word >> 8) & 0xFF,
                    word & 0xFF,
                ]
            )
            take = min(count, 4 - self._pos % 4)
            out += quad[self._pos % 4 : self._pos % 4 + take]
            self._pos += take
            count -= take
            if self._pos == 521 * 4:
                self._advance()
                self._pos = 0
        return bytes(out)


def _read_padded(data: bytes, offset: int, length: int) -> bytes:
    chunk = data[offset : offset + length]
    return chunk + b"\x00" * (length - len(chunk))


def _be32(data: bytes, offset: int = 0) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def reference_gamecube_hash(disc: bytes) -> str:
    """Port of rcheevos rc_hash_gamecube operating on a flat disc image."""
    assert _read_padded(disc, 0x1C, 4) == b"\xc2\x33\x9f\x3d"
    md5 = hashlib.md5(usedforsecurity=False)

    body = _be32(_read_padded(disc, 0x2454, 4))
    trailer = _be32(_read_padded(disc, 0x2458, 4))
    header_size = min(0x2440 + 0x20 + body + trailer, 1024 * 1024)
    md5.update(_read_padded(disc, 0, header_size))

    dol_offset = _be32(_read_padded(disc, 0x420, 4))
    dol_header = _read_padded(disc, dol_offset, 0xD8)
    for ix in range(18):
        seg_offset = _be32(dol_header, ix * 4)
        seg_size = _be32(dol_header, 0x90 + ix * 4)
        if seg_size:
            md5.update(_read_padded(disc, seg_offset, seg_size))
    return md5.hexdigest()


def reference_wii_hash(iso: bytes) -> str:
    """Port of rcheevos rc_hash_wii_disc operating on a flat disc image.

    Mirrors rcheevos exactly, including reading the partition data offset
    field and then seeking with it as an absolute file offset.
    """
    assert _read_padded(iso, 0x18, 4) == b"\x5d\x1c\x9e\xa3"
    md5 = hashlib.md5(usedforsecurity=False)

    encrypted = _read_padded(iso, 0x61, 1) == b"\x00"
    assert encrypted, "reference only implements the encrypted-disc path"

    md5.update(_read_padded(iso, 0, 0x80))
    md5.update(_read_padded(iso, 0x4E000, 4))

    info = struct.unpack(">8I", _read_padded(iso, 0x40000, 32))
    partitions: list[tuple[int, int]] = []
    for j in range(0, 8, 2):
        count, table_off4 = info[j], info[j + 1]
        for i in range(count):
            entry = _read_padded(iso, (table_off4 << 2) + i * 8, 8)
            partitions.append(struct.unpack(">II", entry))
    assert partitions

    for part_off4, part_type in partitions:
        if part_type == 1:  # update partition
            continue
        part_start = part_off4 << 2

        tmd_size, tmd_off4 = struct.unpack(
            ">II", _read_padded(iso, part_start + 0x2A4, 8)
        )
        tmd_size = min(tmd_size, WII_SECTOR_DATA_SIZE)
        md5.update(_read_padded(iso, part_start + (tmd_off4 << 2), tmd_size))

        data_off4, data_size4 = struct.unpack(
            ">II", _read_padded(iso, part_start + 0x2B8, 8)
        )
        part_offset = data_off4 << 2
        part_size = data_size4 << 2

        clusters = min(part_size // WII_SECTOR_SIZE, 1024)
        for ix in range(clusters):
            md5.update(
                _read_padded(
                    iso,
                    part_offset + ix * WII_SECTOR_SIZE + WII_SECTOR_HASH_SIZE,
                    WII_SECTOR_DATA_SIZE,
                )
            )
    return md5.hexdigest()


def _aes_cbc_encrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return encryptor.update(data) + encryptor.finalize()


def encrypt_wii_partition_data(
    data: bytes, key: bytes, hash_patches: list[tuple[int, int, bytes]]
) -> bytes:
    """Rebuild the encrypted on-disc bytes of a Wii partition's data area.

    ``data`` is the decrypted, hashless partition data (a multiple of 0x7C00).
    ``hash_patches`` are (sector, offset, digest) replacements applied to the
    recalculated hash tables before encryption (the wia_except_list_t model).
    """
    n_sectors = len(data) // WII_SECTOR_DATA_SIZE
    out = bytearray()
    for group_start in range(0, n_sectors, 64):
        blocks = []
        for b in range(64):
            s = group_start + b
            if s < n_sectors:
                blocks.append(
                    data[s * WII_SECTOR_DATA_SIZE : (s + 1) * WII_SECTOR_DATA_SIZE]
                )
            else:
                blocks.append(b"\x00" * WII_SECTOR_DATA_SIZE)

        h0_tables = [
            b"".join(
                hashlib.sha1(
                    blocks[b][j * 0x400 : (j + 1) * 0x400], usedforsecurity=False
                ).digest()
                for j in range(31)
            )
            for b in range(64)
        ]
        h1_tables = [
            b"".join(
                hashlib.sha1(h0_tables[sub * 8 + k], usedforsecurity=False).digest()
                for k in range(8)
            )
            for sub in range(8)
        ]
        h2_table = b"".join(
            hashlib.sha1(h1_tables[sub], usedforsecurity=False).digest()
            for sub in range(8)
        )

        headers = []
        for b in range(64):
            header = bytearray(WII_SECTOR_HASH_SIZE)
            header[0:0x26C] = h0_tables[b]
            header[0x280:0x320] = h1_tables[b // 8]
            header[0x340:0x3E0] = h2_table
            headers.append(header)

        for sector, offset, digest in hash_patches:
            if group_start <= sector < group_start + 64:
                headers[sector - group_start][offset : offset + len(digest)] = digest

        for b in range(64):
            if group_start + b >= n_sectors:
                break
            enc_header = _aes_cbc_encrypt(key, b"\x00" * 16, bytes(headers[b]))
            enc_data = _aes_cbc_encrypt(key, enc_header[0x3D0:0x3E0], blocks[b])
            out += enc_header + enc_data
    return bytes(out)


# ---------------------------------------------------------------------------
# Synthetic RVZ / WIA container builder.
# ---------------------------------------------------------------------------


@dataclass
class JunkRun:
    """A disc byte range stored as RVZ-packed junk instead of literal data."""

    disc_offset: int
    size: int
    seed: bytes


@dataclass
class WiiPartitionImage:
    """Decrypted partition data destined for wia_part_t storage."""

    data_offset: int  # absolute disc offset where the encrypted data area starts
    key: bytes
    data: bytes  # decrypted, hashless; a multiple of 0x7C00
    # (group_index, offset_within_group_hash_area, digest) exception entries
    exceptions: list[tuple[int, int, bytes]] = field(default_factory=list)


class RvzBuilder:
    """Build a minimal but spec-conformant RVZ or WIA file for tests."""

    def __init__(
        self,
        disc: bytes,
        *,
        disc_type: int,
        compression: int = COMPRESSION_ZSTD,
        chunk_size: int = 0x8000,
        wia: bool = False,
        partitions: list[WiiPartitionImage] | None = None,
        junk_runs: list[JunkRun] | None = None,
        store_groups_raw: bool = False,
    ) -> None:
        self.disc = disc
        self.disc_type = disc_type
        self.compression = compression
        self.chunk_size = chunk_size
        self.wia = wia
        self.partitions = partitions or []
        self.junk_runs = junk_runs or []
        self.store_groups_raw = store_groups_raw
        if wia:
            assert not self.junk_runs and not store_groups_raw

    def _compress(self, data: bytes) -> bytes:
        if self.compression == COMPRESSION_NONE:
            return data
        if self.compression == COMPRESSION_BZIP2:
            return bz2.compress(data)
        if self.compression == COMPRESSION_LZMA:
            return lzma.compress(data, format=lzma.FORMAT_RAW, filters=_LZMA1_FILTERS)
        if self.compression == COMPRESSION_LZMA2:
            return lzma.compress(data, format=lzma.FORMAT_RAW, filters=_LZMA2_FILTERS)
        if self.compression == COMPRESSION_ZSTD:
            return zstandard.ZstdCompressor(level=3).compress(data)
        raise ValueError(f"unsupported compression {self.compression}")

    @property
    def _compr_data(self) -> bytes:
        if self.compression == COMPRESSION_LZMA:
            return _LZMA1_COMPR_DATA
        if self.compression == COMPRESSION_LZMA2:
            return _LZMA2_COMPR_DATA
        return b""

    def _pack_group_payload(self, plain: bytes, group_disc_start: int) -> tuple[
        bytes,
        int,
    ]:
        """RVZ-pack a group's data, encoding any overlapping junk runs.

        Returns (payload, rvz_packed_size); rvz_packed_size is 0 when the
        group has no junk runs (payload stored unpacked).
        """
        runs = sorted(
            (r for r in self.junk_runs if group_disc_start <= r.disc_offset),
            key=lambda r: r.disc_offset,
        )
        runs = [
            r for r in runs if r.disc_offset + r.size <= group_disc_start + len(plain)
        ]
        if not runs:
            return plain, 0

        packed = bytearray()
        pos = 0
        for run in runs:
            rel = run.disc_offset - group_disc_start
            if rel > pos:
                packed += struct.pack(">I", rel - pos) + plain[pos:rel]
            packed += struct.pack(">I", run.size | 0x80000000) + run.seed
            pos = rel + run.size
        if pos < len(plain):
            packed += struct.pack(">I", len(plain) - pos) + plain[pos:]
        return bytes(packed), len(packed)

    def build(self) -> bytes:
        chunk = self.chunk_size
        iso_size = len(self.disc)

        part_ranges = [
            (
                p.data_offset,
                p.data_offset + len(p.data) // WII_SECTOR_DATA_SIZE * WII_SECTOR_SIZE,
            )
            for p in self.partitions
        ]
        part_ranges.sort()

        # Raw data areas: the complement of the partition data areas.
        raw_ranges: list[tuple[int, int]] = []
        cursor = 0
        for start, end in part_ranges:
            if start > cursor:
                raw_ranges.append((cursor, start))
            cursor = end
        if cursor < iso_size:
            raw_ranges.append((cursor, iso_size))

        group_entries: list[tuple[int, int, int]] = []  # (off4, size_field, packed)
        group_blobs: list[bytes] = []

        def add_group(stream: bytes, compressible: bool, packed_size: int) -> None:
            if not stream:
                group_entries.append((0, 0, 0))
                group_blobs.append(b"")
                return
            if compressible and not self.store_groups_raw:
                blob = self._compress(stream)
                compressed = self.compression != COMPRESSION_NONE
            else:
                blob = stream
                compressed = False
            size_field = len(blob)
            if not self.wia and compressed:
                size_field |= 0x80000000
            group_entries.append((len(blob), size_field, packed_size))
            group_blobs.append(blob)

        raw_entries: list[tuple[int, int, int, int]] = []
        for range_start, range_end in raw_ranges:
            entry_off = max(range_start, 0x80)
            entry_size = range_end - entry_off
            aligned_start = entry_off - (entry_off % WII_SECTOR_SIZE)
            aligned_size = entry_size + (entry_off % WII_SECTOR_SIZE)
            first_group = len(group_entries)
            n_groups = -(-aligned_size // chunk)
            for i in range(n_groups):
                start = aligned_start + i * chunk
                size = min(chunk, aligned_start + aligned_size - start)
                plain = _read_padded(self.disc, start, size)
                if plain.count(0) == len(plain):
                    add_group(b"", True, 0)
                    continue
                payload, packed_size = self._pack_group_payload(plain, start)
                add_group(payload, True, packed_size)
            raw_entries.append((entry_off, entry_size, first_group, n_groups))

        chunk_hashless = chunk // WII_SECTOR_SIZE * WII_SECTOR_DATA_SIZE
        part_entries: list[bytes] = []
        for part in self.partitions:
            n_sectors = len(part.data) // WII_SECTOR_DATA_SIZE
            first_group = len(group_entries)
            n_groups = -(-len(part.data) // chunk_hashless)
            n_lists = max(1, chunk // 0x200000) if not self.wia else chunk // 0x200000
            for i in range(n_groups):
                start = i * chunk_hashless
                plain = part.data[start : start + chunk_hashless]
                group_exceptions = [
                    (offset, digest) for g, offset, digest in part.exceptions if g == i
                ]
                if not group_exceptions and plain.count(0) == len(plain):
                    add_group(b"", True, 0)
                    continue

                except_lists = b""
                # One list per 2 MiB of chunk (a single list below 2 MiB);
                # all of a group's exceptions go in the first list.
                for list_ix in range(n_lists):
                    entries = group_exceptions if list_ix == 0 else []
                    except_lists += struct.pack(">H", len(entries))
                    for offset, digest in entries:
                        except_lists += struct.pack(">H", offset) + digest

                if self.compression == COMPRESSION_NONE:
                    padding = (-len(except_lists)) % 4
                    stream = except_lists + b"\x00" * padding + plain
                    add_group(stream, True, 0)
                else:
                    add_group(except_lists + plain, True, 0)
            part_entries.append(
                part.key
                + struct.pack(
                    ">IIII",
                    part.data_offset // WII_SECTOR_SIZE,
                    n_sectors,
                    first_group,
                    n_groups,
                )
                + struct.pack(">IIII", 0, 0, 0, 0)
            )

        part_blob = b"".join(part_entries)
        raw_blob = self._compress(
            b"".join(struct.pack(">QQII", *entry) for entry in raw_entries)
        )

        # Layout: header 1, header 2, partition entries, group data, raw data
        # entry table, group entry table. Group data offsets must be known
        # before the group table is serialized, so group data comes first.
        part_off = 0x48 + 0xDC
        data_pos = part_off + len(part_blob)
        placed_entries: list[bytes] = []
        body = bytearray()
        for (_blob_size, size_field, packed_size), blob in zip(
            group_entries, group_blobs, strict=True
        ):
            if not blob:
                placed_entries.append(
                    struct.pack(">III" if not self.wia else ">II", 0, 0, 0)[
                        : 12 if not self.wia else 8
                    ]
                )
                continue
            padding = (-data_pos) % 4
            body += b"\x00" * padding
            data_pos += padding
            entry_fields = [data_pos >> 2, size_field]
            if not self.wia:
                entry_fields.append(packed_size)
            placed_entries.append(
                struct.pack(">III" if not self.wia else ">II", *entry_fields)
            )
            body += blob
            data_pos += len(blob)

        group_blob = self._compress(b"".join(placed_entries))
        raw_off = data_pos
        group_off = raw_off + len(raw_blob)
        file_size = group_off + len(group_blob)

        header_2 = struct.pack(
            ">IIiI",
            self.disc_type,
            self.compression,
            0,
            chunk,
        )
        header_2 += _read_padded(self.disc, 0, 0x80)
        header_2 += struct.pack(">II", len(self.partitions), 0x30)
        header_2 += struct.pack(">Q", part_off)
        header_2 += hashlib.sha1(part_blob, usedforsecurity=False).digest()
        header_2 += struct.pack(">IQI", len(raw_entries), raw_off, len(raw_blob))
        header_2 += struct.pack(">IQI", len(group_entries), group_off, len(group_blob))
        compr_data = self._compr_data
        header_2 += bytes([len(compr_data)]) + compr_data.ljust(7, b"\x00")
        assert len(header_2) == 0xDC

        magic = b"WIA\x01" if self.wia else b"RVZ\x01"
        version = 0x01000000
        version_compatible = 0x00090000 if self.wia else 0x00030000
        header_1 = magic + struct.pack(
            ">III", version, version_compatible, len(header_2)
        )
        header_1 += hashlib.sha1(header_2, usedforsecurity=False).digest()
        header_1 += struct.pack(">QQ", iso_size, file_size)
        header_1 += hashlib.sha1(header_1, usedforsecurity=False).digest()
        assert len(header_1) == 0x48

        return bytes(header_1 + header_2 + part_blob + body + raw_blob + group_blob)


# ---------------------------------------------------------------------------
# Synthetic disc fixtures.
# ---------------------------------------------------------------------------


def build_gamecube_disc(size: int = 0x40000) -> bytearray:
    """A tiny GameCube disc with a boot header, apploader and main.dol."""
    disc = bytearray((i * 31 + 7) & 0xFF for i in range(size))
    disc[0:6] = b"GTST01"
    disc[0x1C:0x20] = b"\xc2\x33\x9f\x3d"
    struct.pack_into(">I", disc, 0x420, 0x10000)  # main.dol offset
    struct.pack_into(">I", disc, 0x2454, 0x600)  # apploader body size
    struct.pack_into(">I", disc, 0x2458, 0x80)  # apploader trailer size

    # main.dol header: two code segments and one data segment; rcheevos reads
    # the segment offsets as partition-relative, so these point at disc space.
    dol = 0x10000
    disc[dol : dol + 0xD8] = b"\x00" * 0xD8
    struct.pack_into(">I", disc, dol + 0x00, 0x11000)  # code segment 0 offset
    struct.pack_into(">I", disc, dol + 0x90, 0x900)  # code segment 0 size
    struct.pack_into(">I", disc, dol + 0x04, 0x18000)  # code segment 1 offset
    struct.pack_into(">I", disc, dol + 0x94, 0x1004)  # code segment 1 size
    struct.pack_into(">I", disc, dol + 0x1C, 0x2A000)  # data segment 0 offset
    struct.pack_into(">I", disc, dol + 0xBC, 0x800)  # data segment 0 size
    return disc


def build_wii_disc_and_rvz(
    *,
    compression: int = COMPRESSION_NONE,
    chunk_size: int = 0x20000,
    tmd_size: int = 0x1F4,
    exceptions: list[tuple[int, int, bytes]] | None = None,
) -> tuple[bytes, bytes]:
    """Build a synthetic Wii disc; returns (reference encrypted ISO, RVZ)."""
    iso_size = 0x460000
    disc = bytearray((i * 53 + 11) & 0xFF for i in range(iso_size))
    disc[0:6] = b"RTST01"
    disc[0x18:0x1C] = b"\x5d\x1c\x9e\xa3"
    disc[0x61] = 0x00  # encrypted disc

    game_part = 0x30000
    update_part = 0x38000
    data_offset = 0x20000  # partition-relative data offset field
    part_data_abs = game_part + data_offset  # 0x50000
    n_sectors = 128
    data_size = n_sectors * WII_SECTOR_SIZE

    # Partition info table: one table with an update and a game partition.
    disc[0x40000:0x40030] = b"\x00" * 0x30
    struct.pack_into(">II", disc, 0x40000, 2, 0x40020 >> 2)
    struct.pack_into(">II", disc, 0x40020, update_part >> 2, 1)
    struct.pack_into(">II", disc, 0x40028, game_part >> 2, 0)
    disc[0x4E000:0x4E004] = b"\x00\x00\x00\x01"

    # Game partition header: TMD location/size and data area location/size.
    struct.pack_into(">II", disc, game_part + 0x2A4, tmd_size, 0x2C0 >> 2)
    struct.pack_into(">II", disc, game_part + 0x2B8, data_offset >> 2, data_size >> 2)

    # Update partition header carries plausible fields; rcheevos must skip it
    # entirely (type 1), so none of these bytes may reach the hash.
    struct.pack_into(">II", disc, update_part + 0x2A4, 0x200, 0x2C0 >> 2)
    struct.pack_into(">II", disc, update_part + 0x2B8, data_offset >> 2, 0x8000 >> 2)

    key = bytes(range(16))
    part_data = bytes(
        (i * 97 + 29) & 0xFF for i in range(n_sectors * WII_SECTOR_DATA_SIZE)
    )
    # Zero the partition data area in the raw disc; it is stored (and later
    # reconstructed) through wia_part_t, not through the raw data ranges.
    disc[part_data_abs : part_data_abs + data_size] = b"\x00" * data_size

    exceptions = exceptions or []
    sectors_per_group = chunk_size // WII_SECTOR_SIZE
    hash_patches = [
        (g * sectors_per_group + offset // 0x400, offset % 0x400, digest)
        for g, offset, digest in exceptions
    ]

    iso = bytearray(disc)
    iso[part_data_abs : part_data_abs + data_size] = encrypt_wii_partition_data(
        part_data, key, hash_patches
    )

    rvz = RvzBuilder(
        bytes(disc),
        disc_type=2,
        compression=compression,
        chunk_size=chunk_size,
        partitions=[
            WiiPartitionImage(
                data_offset=part_data_abs,
                key=key,
                data=part_data,
                exceptions=exceptions,
            )
        ],
    ).build()
    return bytes(iso), rvz


# ---------------------------------------------------------------------------
# GameCube tests (issue #3649).
# ---------------------------------------------------------------------------


class TestCalculateGamecubeRaHash:
    """Native hashing of GameCube .rvz / .wia images."""

    @pytest.mark.parametrize(
        "compression",
        [
            COMPRESSION_NONE,
            COMPRESSION_BZIP2,
            COMPRESSION_LZMA,
            COMPRESSION_LZMA2,
            COMPRESSION_ZSTD,
        ],
    )
    def test_rvz_matches_reference_hash_for_each_codec(self, tmp_path, compression):
        disc = build_gamecube_disc()
        path = tmp_path / "game.rvz"
        path.write_bytes(
            RvzBuilder(bytes(disc), disc_type=1, compression=compression).build()
        )

        assert calculate_gamecube_ra_hash(str(path)) == reference_gamecube_hash(
            bytes(disc)
        )

    def test_wia_container_matches_reference_hash(self, tmp_path):
        """WIA (chunk >= 2 MiB, 8-byte group entries) hashes like its RVZ twin."""
        disc = build_gamecube_disc()
        path = tmp_path / "game.wia"
        path.write_bytes(
            RvzBuilder(
                bytes(disc),
                disc_type=1,
                compression=COMPRESSION_LZMA,
                chunk_size=0x200000,
                wia=True,
            ).build()
        )

        assert calculate_gamecube_ra_hash(str(path)) == reference_gamecube_hash(
            bytes(disc)
        )

    def test_groups_stored_raw_despite_compressed_codec(self, tmp_path):
        """RVZ groups without the MSB flag are stored raw even in a zstd file."""
        disc = build_gamecube_disc()
        path = tmp_path / "game.rvz"
        path.write_bytes(
            RvzBuilder(
                bytes(disc),
                disc_type=1,
                compression=COMPRESSION_ZSTD,
                store_groups_raw=True,
            ).build()
        )

        assert calculate_gamecube_ra_hash(str(path)) == reference_gamecube_hash(
            bytes(disc)
        )

    def test_zero_groups_decode_as_zeroes(self, tmp_path):
        """An all-zero chunk is stored with data_size 0 and must read as zeroes."""
        disc = build_gamecube_disc()
        # Zero a whole chunk inside data segment 0 (0x2A000 + 0x800).
        disc[0x28000:0x30000] = b"\x00" * 0x8000
        path = tmp_path / "game.rvz"
        path.write_bytes(RvzBuilder(bytes(disc), disc_type=1).build())

        assert calculate_gamecube_ra_hash(str(path)) == reference_gamecube_hash(
            bytes(disc)
        )

    def test_rvz_packed_junk_regenerates_original_bytes(self, tmp_path):
        """A junk-packed run must regenerate the PRNG bytes the disc held."""
        disc = build_gamecube_disc()
        seed = bytes((i * 17 + 3) & 0xFF for i in range(68))
        junk = SpecLfg(seed).get_bytes(0x4000)
        # Junk sector inside data segment 0's read range, starting 0x8000 into
        # its 0x10000 chunk so the PRNG starts at a sector boundary.
        disc[0x28000 : 0x28000 + 0x4000] = junk
        # Widen data segment 0 to cover literal + junk + literal transitions.
        struct.pack_into(">I", disc, 0x10000 + 0x1C, 0x27000)
        struct.pack_into(">I", disc, 0x10000 + 0xBC, 0x6000)

        path = tmp_path / "game.rvz"
        path.write_bytes(
            RvzBuilder(
                bytes(disc),
                disc_type=1,
                chunk_size=0x10000,
                junk_runs=[JunkRun(disc_offset=0x28000, size=0x4000, seed=seed)],
            ).build()
        )

        assert calculate_gamecube_ra_hash(str(path)) == reference_gamecube_hash(
            bytes(disc)
        )

    def test_returns_empty_for_non_gamecube_disc(self, tmp_path):
        """A Wii disc in the GameCube hasher fails the magic check."""
        _, rvz = build_wii_disc_and_rvz()
        path = tmp_path / "game.rvz"
        path.write_bytes(rvz)

        assert calculate_gamecube_ra_hash(str(path)) == ""

    def test_returns_empty_for_unknown_magic(self, tmp_path):
        path = tmp_path / "game.rvz"
        path.write_bytes(b"NOPE" + b"\x00" * 0x100)

        assert calculate_gamecube_ra_hash(str(path)) == ""

    def test_returns_empty_for_missing_file(self, tmp_path):
        assert calculate_gamecube_ra_hash(str(tmp_path / "missing.rvz")) == ""

    def test_returns_empty_for_truncated_container(self, tmp_path):
        disc = build_gamecube_disc()
        rvz = RvzBuilder(bytes(disc), disc_type=1).build()
        path = tmp_path / "game.rvz"
        path.write_bytes(rvz[: len(rvz) // 2])

        assert calculate_gamecube_ra_hash(str(path)) == ""

    def test_returns_empty_for_corrupt_zstd_group(self, tmp_path):
        """A corrupted compressed group must fail softly, not raise."""
        disc = build_gamecube_disc()
        rvz = bytearray(RvzBuilder(bytes(disc), disc_type=1).build())
        # Group data starts right after the two headers (no partition
        # entries); clobber the first group's zstd frame magic.
        data_start = 0x48 + 0xDC
        rvz[data_start : data_start + 4] = b"\xde\xad\xbe\xef"
        path = tmp_path / "game.rvz"
        path.write_bytes(bytes(rvz))

        assert calculate_gamecube_ra_hash(str(path)) == ""

    def test_returns_empty_for_oversized_chunk_size(self, tmp_path):
        """A crafted chunk size is rejected before any buffer allocation."""
        disc = build_gamecube_disc()
        rvz = bytearray(RvzBuilder(bytes(disc), disc_type=1).build())
        struct.pack_into(">I", rvz, 0x48 + 0x0C, 0x40000000)  # 1 GiB chunks
        path = tmp_path / "game.rvz"
        path.write_bytes(bytes(rvz))

        assert calculate_gamecube_ra_hash(str(path)) == ""

    def test_returns_empty_for_dol_segment_past_disc_end(self, tmp_path):
        """A corrupt main.dol segment size must not stall the scan."""
        disc = build_gamecube_disc()
        struct.pack_into(">I", disc, 0x10000 + 0x90, 0xFFFFFF00)
        path = tmp_path / "game.rvz"
        path.write_bytes(RvzBuilder(bytes(disc), disc_type=1).build())

        assert calculate_gamecube_ra_hash(str(path)) == ""


# ---------------------------------------------------------------------------
# Wii tests (issue #3650).
# ---------------------------------------------------------------------------


class TestCalculateWiiRaHash:
    """Native hashing of Wii .rvz images: hash tree + AES re-encryption."""

    def test_uncompressed_rvz_matches_reference_hash(self, tmp_path):
        iso, rvz = build_wii_disc_and_rvz(compression=COMPRESSION_NONE)
        path = tmp_path / "game.rvz"
        path.write_bytes(rvz)

        assert calculate_wii_ra_hash(str(path)) == reference_wii_hash(iso)

    def test_zstd_rvz_matches_reference_hash(self, tmp_path):
        iso, rvz = build_wii_disc_and_rvz(compression=COMPRESSION_ZSTD)
        path = tmp_path / "game.rvz"
        path.write_bytes(rvz)

        assert calculate_wii_ra_hash(str(path)) == reference_wii_hash(iso)

    def test_small_chunk_zstd_rvz_matches_reference_hash(self, tmp_path):
        """32 KiB chunks: one hash group spans many groups, one list each."""
        iso, rvz = build_wii_disc_and_rvz(
            compression=COMPRESSION_ZSTD, chunk_size=0x8000
        )
        path = tmp_path / "game.rvz"
        path.write_bytes(rvz)

        assert calculate_wii_ra_hash(str(path)) == reference_wii_hash(iso)

    def test_hash_exceptions_are_applied_before_encryption(self, tmp_path):
        """Stored hash exceptions must replace the recalculated tree bytes."""
        exceptions = [
            (0, 0x10, b"\xab" * 20),  # sector 0, inside its H0 table
            (2, 0x400 + 0x290, b"\xcd" * 20),  # group 2, sector 9, H1 area
        ]
        iso, rvz = build_wii_disc_and_rvz(
            compression=COMPRESSION_ZSTD, exceptions=exceptions
        )
        baseline_iso, _ = build_wii_disc_and_rvz(compression=COMPRESSION_ZSTD)
        path = tmp_path / "game.rvz"
        path.write_bytes(rvz)

        expected = reference_wii_hash(iso)
        assert expected != reference_wii_hash(baseline_iso)
        assert calculate_wii_ra_hash(str(path)) == expected

    def test_tmd_size_is_capped_like_rcheevos(self, tmp_path):
        """A TMD size field above 0x7C00 hashes only the first 0x7C00 bytes."""
        iso, rvz = build_wii_disc_and_rvz(tmd_size=0x9000)
        path = tmp_path / "game.rvz"
        path.write_bytes(rvz)

        assert calculate_wii_ra_hash(str(path)) == reference_wii_hash(iso)

    def test_returns_empty_for_non_wii_disc(self, tmp_path):
        """A GameCube disc in the Wii hasher fails the magic check."""
        disc = build_gamecube_disc()
        path = tmp_path / "game.rvz"
        path.write_bytes(RvzBuilder(bytes(disc), disc_type=1).build())

        assert calculate_wii_ra_hash(str(path)) == ""


# ---------------------------------------------------------------------------
# Production PRNG vs the spec implementation.
# ---------------------------------------------------------------------------


class TestLaggedFibonacci:
    """The production junk-data PRNG against an independent spec port."""

    def test_stream_matches_spec_implementation(self):
        seed = bytes((i * 41 + 5) & 0xFF for i in range(68))
        spec = SpecLfg(seed)
        prod = _LaggedFibonacci(seed)

        # Cross several 2084-byte buffer refills to exercise the advance step.
        assert prod.get_bytes(9000) == spec.get_bytes(9000)

    def test_forward_matches_spec_implementation(self):
        seed = bytes((i * 7 + 1) & 0xFF for i in range(68))
        spec = SpecLfg(seed)
        prod = _LaggedFibonacci(seed)
        spec.forward(0x7123)
        prod.forward(0x7123)

        assert prod.get_bytes(600) == spec.get_bytes(600)


# ---------------------------------------------------------------------------
# Real-ROM integration tests. The expected hashes were verified against both
# the RetroAchievements hash database (API_GetGameList) and the shipped
# RAHasher 1.8.3 binary run on the reconstructed disc images.
# ---------------------------------------------------------------------------

_MOCK_ROMS = Path(__file__).parents[3] / "romm_mock" / "library" / "roms"
_REAL_NGC_RVZ = _MOCK_ROMS / "ngc" / "Mario Kart - Double Dash!! (USA).rvz"
_REAL_WII_RVZ = _MOCK_ROMS / "wii" / "Super Mario Galaxy (USA) (En,Fr,Es).rvz"


@pytest.mark.skipif(not _REAL_NGC_RVZ.exists(), reason="mock GameCube RVZ not present")
def test_real_gamecube_rvz_matches_retroachievements_hash():
    """Mario Kart: Double Dash!! (USA), RetroAchievements game 7693."""
    assert (
        calculate_gamecube_ra_hash(str(_REAL_NGC_RVZ))
        == "adad8934d2586d27ec4b653bae52e47b"
    )


@pytest.mark.skipif(not _REAL_WII_RVZ.exists(), reason="mock Wii RVZ not present")
def test_real_wii_rvz_matches_retroachievements_hash():
    """Super Mario Galaxy (USA), RetroAchievements game 189."""
    assert (
        calculate_wii_ra_hash(str(_REAL_WII_RVZ)) == "4e0d0d2f2c5d3c13d758b027bbcc059f"
    )


class TestIsRvzNativeHashFile:
    def test_recognizes_native_extensions(self):
        for ext in RVZ_NATIVE_HASH_EXTENSIONS:
            assert is_rvz_native_hash_file(f"/roms/ngc/game{ext}")
            assert is_rvz_native_hash_file(f"/roms/wii/game{ext.upper()}")

    def test_rejects_other_extensions(self):
        assert not is_rvz_native_hash_file("/roms/ngc/game.iso")
        assert not is_rvz_native_hash_file("/roms/ngc/game.gcm")
        assert not is_rvz_native_hash_file("/roms/wii/game.wbfs")
        assert not is_rvz_native_hash_file("/roms/wii/game.zip")
