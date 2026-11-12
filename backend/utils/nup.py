"""Reads the package records of a NUP container, a decrypted Switch dump format.

Validates the container as NUP SPEC section 6.1 requires and reads only the superblock
and table of contents, never the file contents. Spec: https://github.com/a55uka/nup
"""

import hashlib
import os
import struct
from dataclasses import dataclass
from typing import Final

MAGIC: Final = b"NUP\x01"
TOC_MAGIC: Final = b"TOC\x01"
HEADER_SIZE: Final = 0x80
# Far above any real dump's table of contents; checked before allocating.
MAX_TOC_SIZE: Final = 256 * 1024 * 1024

KIND_NAMES: Final = ("base", "update", "addon", "addon_update", "system")
CODEC_COUNT: Final = 2
NO_DIR: Final = 0xFFFFFFFF
EXTENT_ALIGN: Final = 16
FLAG_STANDALONE_UPDATE: Final = 0x01
# Title ids whose top byte is 0x04 are Switch 2 programs.
SWITCH_2_PLATFORM_BYTE: Final = 0x04

_SUPER: Final = struct.Struct("<4sHHQQ32sQQII16s32s")
_TOC_HEAD: Final = struct.Struct("<4sIQQQQQ")
_PKG: Final = struct.Struct("<QIIIIBBHIQI20x")
_DIR: Final = struct.Struct("<IIIIQ")
_FILE: Final = struct.Struct("<IIQQQ32sBBH12x")


class NupError(ValueError):
    """The file is not a valid NUP v1 container; the message says why."""


@dataclass(frozen=True)
class NupPackage:
    title_id: str
    kind: str
    version: int
    standalone_update: bool


@dataclass(frozen=True)
class NupHeader:
    packages: tuple[NupPackage, ...]

    @property
    def primary(self) -> NupPackage:
        """The first base package, else the first package."""
        return next((p for p in self.packages if p.kind == "base"), self.packages[0])

    @property
    def effective_version(self) -> int:
        """The newest base or update version, else the primary's."""
        versions = [p.version for p in self.packages if p.kind in ("base", "update")]
        return max(versions, default=self.primary.version)

    @property
    def role(self) -> str:
        """What the container holds: "base", "update", "dlc" or "unknown"."""
        kinds = {p.kind for p in self.packages}
        if "base" in kinds:
            return "base"
        if "update" in kinds:
            return "update"
        if kinds <= {"addon", "addon_update"}:
            return "dlc"
        return "unknown"

    @property
    def is_switch2(self) -> bool:
        """Only a 0x04 id is conclusive: Switch 2 Editions keep a Switch 1 base id."""
        return int(self.primary.title_id, 16) >> 56 == SWITCH_2_PLATFORM_BYTE


def looks_like_nup(head: bytes) -> bool:
    """Whether `head` starts with the NUP v1 magic. Does not validate anything else."""
    return head[: len(MAGIC)] == MAGIC


def read_header(path: str | os.PathLike[str]) -> NupHeader:
    """Validate the container at `path` and return its package records.

    Raises NupError for an invalid container; OSError passes through unchanged.
    """
    with open(path, "rb") as fh:
        real_size = os.fstat(fh.fileno()).st_size
        head = fh.read(HEADER_SIZE)
        if len(head) < HEADER_SIZE:
            raise NupError("truncated superblock")
        (
            magic,
            header_size,
            _header_version,
            toc_offset,
            toc_size,
            toc_sha256,
            blob_offset,
            file_size,
            package_count,
            flags,
            _uuid,
            reserved,
        ) = _SUPER.unpack(head)

        if magic[:3] != MAGIC[:3]:
            raise NupError("not a NUP container")
        if magic[3] != MAGIC[3]:
            raise NupError(f"unsupported major version {magic[3]}")
        if toc_size > MAX_TOC_SIZE:
            raise NupError(f"TOC size {toc_size} exceeds {MAX_TOC_SIZE}")
        if header_size < HEADER_SIZE:
            raise NupError(f"header size {header_size:#x} below {HEADER_SIZE:#x}")
        if toc_offset != header_size:
            raise NupError("TOC does not follow the header")
        if blob_offset % EXTENT_ALIGN or blob_offset < toc_offset + toc_size:
            raise NupError("blob region misaligned or overlapping the TOC")
        if file_size != real_size:
            raise NupError(f"recorded size {file_size} != actual size {real_size}")
        if package_count < 1:
            raise NupError("no packages")
        if flags:
            raise NupError(f"unknown superblock flags {flags:#x}")
        if any(reserved):
            raise NupError("superblock reserved bytes not zero")
        if toc_size < _TOC_HEAD.size + package_count * _PKG.size:
            raise NupError("TOC too small for its packages")

        fh.seek(toc_offset)
        toc = fh.read(toc_size)

    if len(toc) != toc_size:
        raise NupError("truncated TOC")
    # Nothing in the TOC is trusted before this check (SPEC 6.1.1).
    if hashlib.sha256(toc).digest() != toc_sha256:
        raise NupError("TOC hash mismatch")
    return _parse_toc(toc, package_count, file_size, blob_offset)


def _parse_toc(
    toc: bytes, package_count: int, file_size: int, blob_offset: int
) -> NupHeader:
    magic, pkg_count, dir_count, file_count, pool_off, pool_size, _reserved = (
        _TOC_HEAD.unpack_from(toc, 0)
    )
    if magic != TOC_MAGIC:
        raise NupError("bad TOC magic")
    if pkg_count != package_count:
        raise NupError("package count differs between superblock and TOC")
    records_end = (
        _TOC_HEAD.size
        + pkg_count * _PKG.size
        + dir_count * _DIR.size
        + file_count * _FILE.size
    )
    if records_end > len(toc):
        raise NupError("TOC truncated")
    if pool_off < records_end or pool_off + pool_size > len(toc):
        raise NupError("string pool outside the TOC")
    if (pool_off - records_end) % 4:
        raise NupError("children array not 4-byte aligned")
    slot_total = (pool_off - records_end) // 4

    packages: list[NupPackage] = []
    pos = _TOC_HEAD.size
    for index in range(pkg_count):
        (
            title_id,
            root_dir,
            exefs_dir,
            romfs_dir,
            version,
            kind,
            pkg_flags,
            reserved1,
            reserved2,
            meta_offset,
            meta_size,
        ) = _PKG.unpack_from(toc, pos)
        pos += _PKG.size
        if kind >= len(KIND_NAMES):
            raise NupError(f"package {index}: unknown kind {kind}")
        if reserved1 or reserved2:
            raise NupError(f"package {index}: reserved bytes not zero")
        if pkg_flags & ~FLAG_STANDALONE_UPDATE:
            raise NupError(f"package {index}: unknown flags {pkg_flags:#x}")
        if root_dir >= dir_count or any(
            d != NO_DIR and d >= dir_count for d in (exefs_dir, romfs_dir)
        ):
            raise NupError(f"package {index}: directory out of bounds")
        if meta_size and meta_offset + meta_size > file_size:
            raise NupError(f"package {index}: meta block out of bounds")
        packages.append(
            NupPackage(
                title_id=f"{title_id:016X}",
                kind=KIND_NAMES[kind],
                version=version,
                standalone_update=bool(pkg_flags & FLAG_STANDALONE_UPDATE),
            )
        )

    used_slots = 0
    for name_off, name_len, first_child, child_count, _r in _DIR.iter_unpack(
        toc[pos : pos + dir_count * _DIR.size]
    ):
        if name_off + name_len > pool_size:
            raise NupError("directory name outside the string pool")
        if first_child + child_count > slot_total:
            raise NupError("directory children out of bounds")
        used_slots += child_count
    if used_slots != slot_total:
        raise NupError("directory child counts do not match the children array")
    pos += dir_count * _DIR.size

    for record in _FILE.iter_unpack(toc[pos : pos + file_count * _FILE.size]):
        name_off, name_len, size, ext_off, ext_size, _sha, codec, codec_flags, _r = (
            record
        )
        if name_off + name_len > pool_size:
            raise NupError("file name outside the string pool")
        if codec >= CODEC_COUNT or codec_flags:
            raise NupError(f"unknown codec {codec} or codec flags {codec_flags}")
        if size == 0:
            if ext_off or ext_size or codec:
                raise NupError("empty file with a non-empty extent")
            continue
        if ext_size == 0:
            raise NupError("non-empty file with an empty extent")
        if ext_off < blob_offset or ext_off + ext_size > file_size:
            raise NupError("file extent out of bounds")
        if ext_off % EXTENT_ALIGN:
            raise NupError("file extent misaligned")

    # SPEC 3.1.2: an update needs its base alongside or the standalone flag.
    has_base = any(p.kind == "base" for p in packages)
    for index, package in enumerate(packages):
        if package.kind == "update" and not has_base and not package.standalone_update:
            raise NupError(f"package {index}: update without base or standalone flag")

    return NupHeader(packages=tuple(packages))
