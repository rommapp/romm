"""Builds minimal NUP v1 containers for tests, following the NUP SPEC sections 2-4.

Each package gets its own empty root dir; `files` are raw files in the first package's
root. `corrupt` damages one field after the container is otherwise well formed.
"""

import hashlib
import struct
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

KIND_BASE: Final = 0
KIND_UPDATE: Final = 1
KIND_ADDON: Final = 2
KIND_ADDON_UPDATE: Final = 3
KIND_SYSTEM: Final = 4
FLAG_STANDALONE_UPDATE: Final = 0x01

HEADER_SIZE: Final = 0x80
NO_DIR: Final = 0xFFFFFFFF

_SUPER = struct.Struct("<4sHHQQ32sQQII16s32s")
_TOC_HEAD = struct.Struct("<4sIQQQQQ")
_PKG = struct.Struct("<QIIIIBBHIQI20x")
_DIR = struct.Struct("<IIIIQ")
_FILE = struct.Struct("<IIQQQ32sBBH12x")

Corruption = Literal[
    "magic", "major", "toc_hash", "file_size", "toc_size_cap", "meta_oob"
]


@dataclass(frozen=True)
class Pkg:
    title_id: int
    kind: int = KIND_BASE
    version: int = 0
    flags: int = 0


def _align16(value: int) -> int:
    return (value + 15) & ~15


def build_nup(
    packages: Sequence[Pkg],
    *,
    files: Sequence[tuple[str, bytes]] = (),
    corrupt: Corruption | None = None,
) -> bytes:
    files = sorted(files, key=lambda f: f[0].encode())
    dir_count = len(packages)
    file_count = len(files)

    pool = bytearray()
    name_refs: list[tuple[int, int]] = []
    for name, _ in files:
        encoded = name.encode()
        name_refs.append((len(pool), len(encoded)))
        pool += encoded

    pool_off = (
        _TOC_HEAD.size
        + dir_count * _PKG.size
        + dir_count * _DIR.size
        + file_count * _FILE.size
        + file_count * 4
    )
    toc_size = pool_off + len(pool)
    blob_offset = _align16(HEADER_SIZE + toc_size)

    blob = bytearray()
    extents: list[int] = []
    for _, data in files:
        if not data:
            extents.append(0)
            continue
        blob += b"\0" * (_align16(len(blob)) - len(blob))
        extents.append(blob_offset + len(blob))
        blob += data
    file_size = blob_offset + len(blob)

    toc = bytearray(
        _TOC_HEAD.pack(
            b"TOC\x01", len(packages), dir_count, file_count, pool_off, len(pool), 0
        )
    )
    for index, pkg in enumerate(packages):
        meta_offset, meta_size = (
            (file_size, 1) if corrupt == "meta_oob" and index == 0 else (0, 0)
        )
        toc += _PKG.pack(
            pkg.title_id,
            index,
            NO_DIR,
            NO_DIR,
            pkg.version,
            pkg.kind,
            pkg.flags,
            0,
            0,
            meta_offset,
            meta_size,
        )
    for index in range(dir_count):
        first, count = (0, file_count) if index == 0 else (file_count, 0)
        toc += _DIR.pack(0, 0, first, count, 0)
    for (name_off, name_len), (_, data), extent in zip(
        name_refs, files, extents, strict=True
    ):
        toc += _FILE.pack(
            name_off,
            name_len,
            len(data),
            extent,
            len(data),
            hashlib.sha256(data).digest(),
            0,
            0,
            0,
        )
    toc += struct.pack(f"<{file_count}I", *(dir_count + i for i in range(file_count)))
    toc += pool
    assert len(toc) == toc_size

    toc_sha = hashlib.sha256(toc).digest()
    if corrupt == "toc_hash":
        toc[_TOC_HEAD.size] ^= 0xFF

    magic = {"magic": b"XUP\x01", "major": b"NUP\x02"}.get(corrupt or "", b"NUP\x01")
    superblock = _SUPER.pack(
        magic,
        HEADER_SIZE,
        1,
        HEADER_SIZE,
        256 * 1024 * 1024 + 1 if corrupt == "toc_size_cap" else toc_size,
        toc_sha,
        blob_offset,
        file_size + 1 if corrupt == "file_size" else file_size,
        len(packages),
        0,
        b"\x11" * 16,
        b"\0" * 32,
    )

    padding = b"\0" * (blob_offset - HEADER_SIZE - toc_size)
    return superblock + bytes(toc) + padding + bytes(blob)
