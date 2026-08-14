import hashlib
import struct
import zlib

import pytest

from utils.psp_hasher import (
    PSP_NATIVE_HASH_EXTENSIONS,
    _lz4_decompress_block,
    calculate_psp_ra_hash,
    is_psp_native_hash_file,
)

ISO_SECTOR_SIZE = 2048

# Sector layout used by the synthetic ISO builder below.
_ROOT_LBA = 18
_PSP_GAME_LBA = 19
_SYSDIR_LBA = 20
_PARAM_LBA = 21
_EBOOT_LBA = 22


def _dir_record(name: bytes, lba: int, size: int, is_dir: bool) -> bytes:
    """Build a minimal ISO9660 directory record (only the fields we parse)."""
    record_len = 33 + len(name)
    if record_len % 2:
        record_len += 1  # records are padded to an even length
    record = bytearray(record_len)
    record[0] = record_len
    struct.pack_into("<I", record, 2, lba)
    struct.pack_into("<I", record, 10, size)
    record[25] = 0x02 if is_dir else 0x00
    record[32] = len(name)
    record[33 : 33 + len(name)] = name
    return bytes(record)


def _extent(records: list[bytes]) -> bytes:
    data = b"".join(records)
    assert len(data) <= ISO_SECTOR_SIZE
    return data + b"\x00" * (ISO_SECTOR_SIZE - len(data))


def build_psp_iso(param_sfo: bytes, eboot_bin: bytes) -> bytes:
    """Build a tiny but valid-enough ISO9660 holding the two PSP hash files."""
    eboot_sectors = max(1, (len(eboot_bin) + ISO_SECTOR_SIZE - 1) // ISO_SECTOR_SIZE)
    total_sectors = _EBOOT_LBA + eboot_sectors
    iso = bytearray(total_sectors * ISO_SECTOR_SIZE)

    pvd = bytearray(ISO_SECTOR_SIZE)
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1
    pvd[156 : 156 + 34] = _dir_record(b"\x00", _ROOT_LBA, ISO_SECTOR_SIZE, True)
    iso[16 * ISO_SECTOR_SIZE : 17 * ISO_SECTOR_SIZE] = pvd

    iso[_ROOT_LBA * ISO_SECTOR_SIZE : (_ROOT_LBA + 1) * ISO_SECTOR_SIZE] = _extent(
        [
            _dir_record(b"\x00", _ROOT_LBA, ISO_SECTOR_SIZE, True),
            _dir_record(b"\x01", _ROOT_LBA, ISO_SECTOR_SIZE, True),
            _dir_record(b"PSP_GAME", _PSP_GAME_LBA, ISO_SECTOR_SIZE, True),
        ]
    )
    iso[_PSP_GAME_LBA * ISO_SECTOR_SIZE : (_PSP_GAME_LBA + 1) * ISO_SECTOR_SIZE] = (
        _extent(
            [
                _dir_record(b"\x00", _PSP_GAME_LBA, ISO_SECTOR_SIZE, True),
                _dir_record(b"\x01", _ROOT_LBA, ISO_SECTOR_SIZE, True),
                # ";1" version suffix must be stripped during lookup
                _dir_record(b"PARAM.SFO;1", _PARAM_LBA, len(param_sfo), False),
                _dir_record(b"SYSDIR", _SYSDIR_LBA, ISO_SECTOR_SIZE, True),
            ]
        )
    )
    iso[_SYSDIR_LBA * ISO_SECTOR_SIZE : (_SYSDIR_LBA + 1) * ISO_SECTOR_SIZE] = _extent(
        [
            _dir_record(b"\x00", _SYSDIR_LBA, ISO_SECTOR_SIZE, True),
            _dir_record(b"\x01", _PSP_GAME_LBA, ISO_SECTOR_SIZE, True),
            _dir_record(b"EBOOT.BIN;1", _EBOOT_LBA, len(eboot_bin), False),
        ]
    )

    iso[
        _PARAM_LBA * ISO_SECTOR_SIZE : _PARAM_LBA * ISO_SECTOR_SIZE + len(param_sfo)
    ] = param_sfo
    iso[
        _EBOOT_LBA * ISO_SECTOR_SIZE : _EBOOT_LBA * ISO_SECTOR_SIZE + len(eboot_bin)
    ] = eboot_bin
    return bytes(iso)


def _lz4_literal_block(data: bytes) -> bytes:
    """Encode ``data`` as a single literals-only LZ4 block (no matches)."""
    out = bytearray()
    out.append((15 if len(data) >= 15 else len(data)) << 4)
    if len(data) >= 15:
        remaining = len(data) - 15
        while remaining >= 255:
            out.append(255)
            remaining -= 255
        out.append(remaining)
    out += data
    return bytes(out)


def build_ciso(iso: bytes, lz4: bool = False, block_size: int = 2048) -> bytes:
    """Wrap a raw ISO in a CISO (.cso) or ZISO (.zso) container."""
    num_blocks = (len(iso) + block_size - 1) // block_size
    header = bytearray(24)
    header[:4] = b"ZISO" if lz4 else b"CISO"
    struct.pack_into("<I", header, 4, 24)
    struct.pack_into("<Q", header, 8, len(iso))
    struct.pack_into("<I", header, 16, block_size)
    header[20] = 1

    index: list[int] = []
    body = bytearray()
    pos = 24 + (num_blocks + 1) * 4
    for i in range(num_blocks):
        block = iso[i * block_size : (i + 1) * block_size]
        if len(block) < block_size:
            block = block + b"\x00" * (block_size - len(block))
        if lz4:
            # Store as a (non-plain) LZ4 block so the decoder path is exercised.
            stored = _lz4_literal_block(block)
            index.append(pos)
        else:
            compressor = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
            compressed = compressor.compress(block) + compressor.flush()
            if len(compressed) >= block_size:
                stored = block
                index.append(pos | 0x80000000)  # plain block flag
            else:
                stored = compressed
                index.append(pos)
        body += stored
        pos += len(stored)
    index.append(pos)  # sentinel pointing past the last block

    out = bytearray(header)
    for entry in index:
        out += struct.pack("<I", entry)
    out += body
    return bytes(out)


def build_dax(iso: bytes) -> bytes:
    """Wrap a raw ISO in a DAX (.dax) container (zlib blocks, no NC areas)."""
    block_size = 0x2000
    num_blocks = (len(iso) + block_size - 1) // block_size
    offsets: list[int] = []
    sizes: list[int] = []
    body = bytearray()
    pos = 32 + num_blocks * 4 + num_blocks * 2
    for i in range(num_blocks):
        block = iso[i * block_size : (i + 1) * block_size]
        if len(block) < block_size:
            block = block + b"\x00" * (block_size - len(block))
        compressed = zlib.compress(block, 9)
        offsets.append(pos)
        sizes.append(len(compressed))
        body += compressed
        pos += len(compressed)

    header = bytearray(32)
    header[:4] = b"DAX\x00"
    struct.pack_into("<I", header, 4, len(iso))
    struct.pack_into("<I", header, 8, 1)  # version
    struct.pack_into("<I", header, 12, 0)  # nc_areas

    out = bytearray(header)
    for offset in offsets:
        out += struct.pack("<I", offset)
    for size in sizes:
        out += struct.pack("<H", size)
    out += body
    return bytes(out)


@pytest.fixture
def psp_files():
    """Deterministic PARAM.SFO / EBOOT.BIN bytes and their expected RA hash."""
    param_sfo = bytes((i * 37 + 11) & 0xFF for i in range(800))
    eboot_bin = bytes((i * 53 + 7) & 0xFF for i in range(5000)) + b"\x00" * 1000
    expected = hashlib.md5(param_sfo + eboot_bin, usedforsecurity=False).hexdigest()
    return param_sfo, eboot_bin, expected


class TestCalculatePspRaHash:
    """End-to-end native hashing of each compressed-ISO container format."""

    def test_cso_matches_expected_hash(self, tmp_path, psp_files):
        param_sfo, eboot_bin, expected = psp_files
        iso = build_psp_iso(param_sfo, eboot_bin)
        path = tmp_path / "game.cso"
        path.write_bytes(build_ciso(iso, lz4=False))

        assert calculate_psp_ra_hash(str(path)) == expected

    def test_zso_matches_expected_hash(self, tmp_path, psp_files):
        param_sfo, eboot_bin, expected = psp_files
        iso = build_psp_iso(param_sfo, eboot_bin)
        path = tmp_path / "game.zso"
        path.write_bytes(build_ciso(iso, lz4=True))

        assert calculate_psp_ra_hash(str(path)) == expected

    def test_dax_matches_expected_hash(self, tmp_path, psp_files):
        param_sfo, eboot_bin, expected = psp_files
        iso = build_psp_iso(param_sfo, eboot_bin)
        path = tmp_path / "game.dax"
        path.write_bytes(build_dax(iso))

        assert calculate_psp_ra_hash(str(path)) == expected

    def test_hash_is_independent_of_container(self, tmp_path, psp_files):
        """A .cso and the equivalent .dax must yield the same RA hash."""
        param_sfo, eboot_bin, _ = psp_files
        iso = build_psp_iso(param_sfo, eboot_bin)
        cso = tmp_path / "game.cso"
        dax = tmp_path / "game.dax"
        cso.write_bytes(build_ciso(iso, lz4=False))
        dax.write_bytes(build_dax(iso))

        assert calculate_psp_ra_hash(str(cso)) == calculate_psp_ra_hash(str(dax))

    def test_returns_empty_for_unknown_magic(self, tmp_path):
        path = tmp_path / "game.cso"
        path.write_bytes(b"NOPE" + b"\x00" * 64)

        assert calculate_psp_ra_hash(str(path)) == ""

    def test_returns_empty_for_missing_file(self, tmp_path):
        assert calculate_psp_ra_hash(str(tmp_path / "does-not-exist.cso")) == ""

    def test_returns_empty_when_psp_files_absent(self, tmp_path):
        """A valid ISO without PSP_GAME/PARAM.SFO can't be hashed natively."""
        iso = bytearray(20 * ISO_SECTOR_SIZE)
        pvd = bytearray(ISO_SECTOR_SIZE)
        pvd[0] = 1
        pvd[1:6] = b"CD001"
        pvd[156 : 156 + 34] = _dir_record(b"\x00", _ROOT_LBA, ISO_SECTOR_SIZE, True)
        iso[16 * ISO_SECTOR_SIZE : 17 * ISO_SECTOR_SIZE] = pvd
        iso[_ROOT_LBA * ISO_SECTOR_SIZE : (_ROOT_LBA + 1) * ISO_SECTOR_SIZE] = _extent(
            [
                _dir_record(b"\x00", _ROOT_LBA, ISO_SECTOR_SIZE, True),
                _dir_record(b"\x01", _ROOT_LBA, ISO_SECTOR_SIZE, True),
            ]
        )
        path = tmp_path / "movie.cso"
        path.write_bytes(build_ciso(bytes(iso), lz4=False))

        assert calculate_psp_ra_hash(str(path)) == ""


class TestLz4DecompressBlock:
    """The hand-rolled LZ4 block decoder used for ZISO."""

    def test_literals_only_round_trip(self):
        data = bytes(range(256)) * 8  # 2048 bytes, all literals
        block = _lz4_literal_block(data)

        assert _lz4_decompress_block(block, len(data)) == data

    def test_match_run_decodes(self):
        """A single literal followed by a long back-reference (RLE)."""
        block = bytearray()
        block.append((1 << 4) | 0x0F)  # 1 literal, extended match length
        block.append(0x41)
        block += struct.pack("<H", 1)  # match offset 1
        remaining = 2047 - 4 - 15  # total match length 2047, minus base 4 and nibble 15
        while remaining >= 255:
            block.append(255)
            remaining -= 255
        block.append(remaining)

        assert _lz4_decompress_block(bytes(block), 2048) == b"\x41" * 2048


class TestIsPspNativeHashFile:
    def test_recognizes_native_extensions(self):
        for ext in PSP_NATIVE_HASH_EXTENSIONS:
            assert is_psp_native_hash_file(f"/roms/psp/game{ext}")
            assert is_psp_native_hash_file(f"/roms/psp/game{ext.upper()}")

    def test_rejects_other_extensions(self):
        assert not is_psp_native_hash_file("/roms/psp/game.iso")
        assert not is_psp_native_hash_file("/roms/psp/game.chd")
        assert not is_psp_native_hash_file("/roms/psp/game.zip")
