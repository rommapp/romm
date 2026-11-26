"""Builds minimal NUP v1 containers for tests, following the NUP SPEC sections 2-4."""

import hashlib
import struct
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from utils.nup import (
    DIR_RECORD,
    EXTENT_ALIGN,
    FILE_RECORD,
    HEADER_SIZE,
    KIND_NAMES,
    MAGIC,
    MAX_PACKAGE_COUNT,
    MAX_TOC_SIZE,
    NO_DIR,
    PACKAGE_RECORD,
    SUPERBLOCK,
    TOC_HEAD,
    TOC_MAGIC,
)

KIND_BASE: Final = KIND_NAMES.index("base")
KIND_UPDATE: Final = KIND_NAMES.index("update")
KIND_ADDON: Final = KIND_NAMES.index("addon")
KIND_ADDON_UPDATE: Final = KIND_NAMES.index("addon_update")
KIND_SYSTEM: Final = KIND_NAMES.index("system")

Corruption = Literal[
    "magic",
    "major",
    "toc_hash",
    "file_size",
    "toc_size_cap",
    "package_count_cap",
    "meta_oob",
]


@dataclass(frozen=True)
class Pkg:
    title_id: int
    kind: int = KIND_BASE
    version: int = 0
    flags: int = 0


def _align(value: int) -> int:
    return (value + EXTENT_ALIGN - 1) & -EXTENT_ALIGN


def build_nup(
    packages: Sequence[Pkg],
    *,
    files: Sequence[tuple[str, bytes]] = (),
    corrupt: Corruption | None = None,
) -> bytes:
    """Build a container in which every package gets its own empty root dir.

    Args:
        files: Raw files placed in the first package's root dir.
        corrupt: One field to damage in an otherwise well-formed container.
    """
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
        TOC_HEAD.size
        + dir_count * PACKAGE_RECORD.size
        + dir_count * DIR_RECORD.size
        + file_count * FILE_RECORD.size
        + file_count * 4
    )
    toc_size = pool_off + len(pool)
    blob_offset = _align(HEADER_SIZE + toc_size)

    blob = bytearray()
    extents: list[int] = []
    for _, data in files:
        if not data:
            extents.append(0)
            continue
        blob += b"\0" * (_align(len(blob)) - len(blob))
        extents.append(blob_offset + len(blob))
        blob += data
    file_size = blob_offset + len(blob)

    toc = bytearray(
        TOC_HEAD.pack(
            TOC_MAGIC, len(packages), dir_count, file_count, pool_off, len(pool), 0
        )
    )
    for index, pkg in enumerate(packages):
        meta_offset, meta_size = (
            (file_size, 1) if corrupt == "meta_oob" and index == 0 else (0, 0)
        )
        toc += PACKAGE_RECORD.pack(
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
        toc += DIR_RECORD.pack(0, 0, first, count, 0)
    for (name_off, name_len), (_, data), extent in zip(
        name_refs, files, extents, strict=True
    ):
        toc += FILE_RECORD.pack(
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
        toc[TOC_HEAD.size] ^= 0xFF

    magic = {"magic": b"XUP\x01", "major": b"NUP\x02"}.get(corrupt or "", MAGIC)
    superblock = SUPERBLOCK.pack(
        magic,
        HEADER_SIZE,
        1,
        HEADER_SIZE,
        MAX_TOC_SIZE + 1 if corrupt == "toc_size_cap" else toc_size,
        toc_sha,
        blob_offset,
        file_size + 1 if corrupt == "file_size" else file_size,
        MAX_PACKAGE_COUNT + 1 if corrupt == "package_count_cap" else len(packages),
        0,
        b"\x11" * 16,
        b"\0" * 32,
    )

    padding = b"\0" * (blob_offset - HEADER_SIZE - toc_size)
    return superblock + bytes(toc) + padding + bytes(blob)
