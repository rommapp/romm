# trunk-ignore-all(bandit/B404)

import bz2
import fnmatch
import io
import lzma
import os
import re
import subprocess
import tarfile
import tempfile
import threading
import time
import zipfile
import zlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Final, Protocol, Self

import magic
import zipfile_inflate64  # trunk-ignore(ruff/F401): Patches zipfile to support Enhanced Deflate

from config import SEVEN_ZIP_TIMEOUT
from logger.logger import log
from utils.filesystem import (
    ARCHIVE_FORMAT_BY_SUFFIX,
    COMPRESSED_FILE_EXTENSIONS,
    ArchiveFormat,
)

# 7zip archives are read through 7zz.
SEVEN_ZIP_PATH = "/usr/bin/7zz"
# RAR archives are read through bsdtar.
BSDTAR_PATH = "/usr/bin/bsdtar"

RAR_FILE_EXTENSIONS: Final = tuple(
    suffix for suffix, fmt in ARCHIVE_FORMAT_BY_SUFFIX if fmt == "rar"
)

# libarchive escapes the backslash and every byte outside printable ASCII as a
# 3-digit octal sequence in the mtree listings we parse RAR members from.
_MTREE_OCTAL_ESCAPE: Final = re.compile(rb"\\([0-7]{3})")

# bsdtar treats member arguments as glob patterns, where a backslash escapes
# the character that follows it.
_BSDTAR_GLOB_METACHARACTERS: Final = frozenset("\\*?[]")

# Current libmagic reports gzip as application/gzip, older releases as x-gzip.
ARCHIVE_FORMAT_BY_MIME: Final[dict[str, ArchiveFormat]] = {
    "application/zip": "zip",
    "application/x-tar": "tar",
    "application/gzip": "gzip",
    "application/x-gzip": "gzip",
    "application/x-bzip2": "bz2",
    "application/x-xz": "xz",
    "application/x-7z-compressed": "7z",
}

COMPRESSED_MIME_TYPES: Final = frozenset(ARCHIVE_FORMAT_BY_MIME)

# What tarfile and the stream decompressors raise on a damaged or foreign file.
_DECOMPRESS_ERRORS: Final = (
    tarfile.TarError,
    OSError,
    EOFError,
    zlib.error,
    lzma.LZMAError,
)

# zlib's window bits for gzip framing, and the magic that opens a gzip member.
_GZIP_WBITS: Final = 31
_GZIP_MAGIC: Final = b"\x1f\x8b"

# CHD (Compressed Hunks of Data) v5 format constants
# See: https://github.com/mamedev/mame/blob/master/src/lib/util/chd.h
CHD_SIGNATURE: Final = b"MComprHD"
CHD_SIGNATURE_LENGTH: Final = 8
CHD_MIN_HEADER_LENGTH: Final = 16  # Minimum to read signature and version
CHD_V5_HEADER_LENGTH: Final = 124  # Total v5 header size
CHD_VERSION_OFFSET: Final = 12  # Bytes offset for version field
CHD_VERSION_LENGTH: Final = 4  # Version is a uint32
CHD_V5_SHA1_OFFSET: Final = 84  # Combined raw+meta SHA1 offset in v5
CHD_V5_SHA1_LENGTH: Final = 20  # SHA1 is 20 bytes
CHD_V5_VERSION: Final = 5  # CHD v5 identifier
CHD_MIME_TYPE: Final = "application/x-mame-chd"

# Hashing runs in threads and hashlib/zlib release the GIL per chunk, so small
# chunks make concurrent scans contend instead of overlapping.
FILE_READ_CHUNK_SIZE: Final = 1024 * 256
_MIME_DETECTOR = magic.Magic(mime=True)
_MIME_DETECTOR_LOCK = threading.Lock()


class ArchiveReadError(Exception):
    """An archive's members could not be fully read."""


@contextmanager
def _kill_at_deadline(
    process: subprocess.Popen[bytes], deadline: float
) -> Iterator[threading.Event]:
    """Kill `process` at `deadline`, even while a read of its stdout is blocked.

    Yields an event that is set once the deadline has passed.
    """
    expired = threading.Event()
    finished = threading.Event()

    def _watch() -> None:
        if not finished.wait(max(0.0, deadline - time.monotonic())):
            expired.set()
            process.kill()

    watcher = threading.Thread(target=_watch, name="7z-deadline", daemon=True)
    watcher.start()
    try:
        yield expired
    finally:
        finished.set()
        watcher.join()


def detect_mime_type(file_path: os.PathLike[str] | str) -> str:
    """Detect MIME type via libmagic; returns empty string on error."""
    try:
        with _MIME_DETECTOR_LOCK:
            return _MIME_DETECTOR.from_file(file_path)
    except OSError, magic.MagicException:
        return ""


def is_compressed_file(file_path: str | Path) -> bool:
    file_type = detect_mime_type(file_path)
    return file_type in COMPRESSED_MIME_TYPES or str(file_path).lower().endswith(
        tuple(COMPRESSED_FILE_EXTENSIONS)
    )


def read_basic_file(file_path: os.PathLike[str]) -> Iterator[bytes]:
    with open(file_path, "rb") as f:
        while chunk := f.read(FILE_READ_CHUNK_SIZE):
            yield chunk


def detect_archive_format(
    file_path: Path, mime_type: str | None = None
) -> ArchiveFormat | None:
    """Pick an archive format by suffix, then by MIME type.

    Args:
        mime_type: The file's libmagic MIME type, detected here when not given.
    """
    name = file_path.name.lower()
    for suffix, archive_format in ARCHIVE_FORMAT_BY_SUFFIX:
        if name.endswith(suffix):
            return archive_format
    if mime_type is None:
        mime_type = detect_mime_type(file_path)
    return ARCHIVE_FORMAT_BY_MIME.get(mime_type)


def _read_deadline() -> float:
    return time.monotonic() + SEVEN_ZIP_TIMEOUT


def _check_deadline(deadline: float, file_path: Path) -> None:
    if time.monotonic() > deadline:
        raise ArchiveReadError(
            f"Reading {file_path} timed out after {SEVEN_ZIP_TIMEOUT}s; "
            "raise SEVEN_ZIP_TIMEOUT for large archives"
        )


def read_zip_file(file_path: Path) -> Iterator[Iterator[bytes]]:
    """Yield the largest zip member's chunks, raising `ArchiveReadError` if it can't be read."""
    deadline = _read_deadline()
    try:
        with zipfile.ZipFile(file_path, "r") as z:
            largest_file = max(
                (info for info in z.infolist() if not info.is_dir()),
                key=lambda x: x.file_size,
                default=None,
            )
            if largest_file is None:
                raise ArchiveReadError(f"Zip {file_path} has no members")
            if _undecodable_zip_method(z, [largest_file]) is None:
                with z.open(largest_file, "r") as f:
                    yield _iter_chunks(f, file_path, largest_file.filename, deadline)
                return
    except (zipfile.BadZipFile, RuntimeError, OSError, ValueError) as e:
        raise ArchiveReadError(f"Error reading zip {file_path}: {e}") from e
    # zipfile can't decode every compression method, and 7zz reads them all.
    yield from read_7z_or_rar_file(file_path)


def _iter_tar_candidates(
    tf: tarfile.TarFile, file_path: Path, deadline: float
) -> Iterator[Iterator[bytes]]:
    """Yield each regular member larger than every one before it, in one pass.

    A compressed tarball can't seek back to its largest member without
    decompressing again, so every new largest is streamed as it passes.
    """
    largest_size = -1
    try:
        for member in tf:
            _check_deadline(deadline, file_path)
            if not member.isfile() or member.size <= largest_size:
                continue
            largest_size = member.size
            ef = tf.extractfile(member)
            if ef is None:
                raise ArchiveReadError(f"Can't extract {member.name}")
            with ef:
                yield _iter_chunks(ef, file_path, member.name, deadline)
    except _DECOMPRESS_ERRORS as e:
        raise ArchiveReadError(f"Error reading tar {file_path}: {e}") from e
    if largest_size < 0:
        raise ArchiveReadError(f"Tar {file_path} has no members")


def read_tar_file(file_path: Path) -> Iterator[Iterator[bytes]]:
    """Yield ever-larger tar members' chunks, raising `ArchiveReadError` if one can't be read."""
    deadline = _read_deadline()
    try:
        tf = tarfile.open(file_path, "r|*")
    except _DECOMPRESS_ERRORS as e:
        raise ArchiveReadError(f"Error reading tar {file_path}: {e}") from e
    with tf:
        yield from _iter_tar_candidates(tf, file_path, deadline)


def _open_tarball(file_path: Path) -> tarfile.TarFile | None:
    try:
        tf = tarfile.open(file_path, "r|*")
    except _DECOMPRESS_ERRORS:
        return None
    # tarfile opens a zero-filled first block as an empty archive, which a
    # compressed disc image can start with, so require a first member.
    try:
        if tf.next() is not None:
            return tf
    except _DECOMPRESS_ERRORS:
        pass
    tf.close()
    return None


def _iter_gzip_content(file_path: Path, deadline: float) -> Iterator[bytes]:
    """Decompress every gzip member, ignoring trailing bytes the way gunzip does."""
    with open(file_path, "rb") as f:
        decompressor = zlib.decompressobj(wbits=_GZIP_WBITS)
        data = f.read(FILE_READ_CHUNK_SIZE)
        while True:
            _check_deadline(deadline, file_path)
            chunk = decompressor.decompress(data, FILE_READ_CHUNK_SIZE)
            if chunk:
                yield chunk
            if decompressor.eof:
                data = decompressor.unused_data
                while len(data) < len(_GZIP_MAGIC) and (more := f.read(1)):
                    data += more
                if not data.startswith(_GZIP_MAGIC):
                    return
                decompressor = zlib.decompressobj(wbits=_GZIP_WBITS)
                continue
            data = decompressor.unconsumed_tail
            if not data and not chunk:
                data = f.read(FILE_READ_CHUNK_SIZE)
                if not data:
                    raise EOFError(
                        "Compressed file ended before the end-of-stream marker"
                    )


def _iter_opened_content(
    opener: Callable[[Path], io.BufferedIOBase],
) -> Callable[[Path, float], Iterator[bytes]]:
    def _iter_content(file_path: Path, deadline: float) -> Iterator[bytes]:
        with opener(file_path) as f:
            yield from _iter_chunks(f, file_path, file_path.name, deadline)

    return _iter_content


def _wrap_read_errors(chunks: Iterator[bytes], file_path: Path) -> Iterator[bytes]:
    try:
        yield from chunks
    except _DECOMPRESS_ERRORS as e:
        raise ArchiveReadError(f"Error reading {file_path}: {e}") from e


def _read_compressed_stream(
    file_path: Path, iter_content: Callable[[Path, float], Iterator[bytes]]
) -> Iterator[Iterator[bytes]]:
    deadline = _read_deadline()
    # A tarball under a single-stream suffix (game.gb.gz) hashes like a .tar.gz.
    tarball = _open_tarball(file_path)
    if tarball is not None:
        with tarball:
            yield from _iter_tar_candidates(tarball, file_path, deadline)
        return
    yield _wrap_read_errors(iter_content(file_path, deadline), file_path)


def read_gz_file(file_path: Path) -> Iterator[Iterator[bytes]]:
    return _read_compressed_stream(file_path, _iter_gzip_content)


def read_bz2_file(file_path: Path) -> Iterator[Iterator[bytes]]:
    return _read_compressed_stream(file_path, _iter_opened_content(bz2.BZ2File))


def read_xz_file(file_path: Path) -> Iterator[Iterator[bytes]]:
    return _read_compressed_stream(file_path, _iter_opened_content(lzma.LZMAFile))


def read_7z_or_rar_file(file_path: Path) -> Iterator[Iterator[bytes]]:
    """Yield the largest member's chunks through 7zz (bsdtar for RAR).

    Raises `ArchiveReadError` if it can't be read.
    """
    largest_file = max(
        _list_archive_file_members(file_path), key=lambda e: e[1], default=None
    )
    if largest_file is None:
        raise ArchiveReadError(f"Archive {file_path} has no members")
    for _name, _size, chunks in _stream_archive_members(file_path, [largest_file]):
        yield chunks


# Each reader yields the chunks of successively larger members, so the last one
# is the largest; a format that knows its largest member up front yields once.
LARGEST_MEMBER_READERS: Final[
    dict[ArchiveFormat, Callable[[Path], Iterator[Iterator[bytes]]]]
] = {
    "zip": read_zip_file,
    "tar": read_tar_file,
    "gzip": read_gz_file,
    "bz2": read_bz2_file,
    "xz": read_xz_file,
    "7z": read_7z_or_rar_file,
    "rar": read_7z_or_rar_file,
}


class Hasher(Protocol):
    def update(self, chunk: bytes | bytearray, /) -> None: ...

    def copy(self) -> Self: ...


def hash_largest_member[H: Hasher](
    file_path: Path, hasher: H, mime_type: str | None = None
) -> H | None:
    """Feed a copy of `hasher` with a compressed file's content (its largest member).

    Args:
        mime_type: The file's libmagic MIME type, detected here when not given.

    Returns:
        The fed copy, or None if the file is not a known archive, holds no
        content, or can't be read in full. `hasher` itself is never fed.
    """
    archive_format = detect_archive_format(file_path, mime_type)
    if archive_format is None:
        return None
    fed: H | None = None
    try:
        for chunks in LARGEST_MEMBER_READERS[archive_format](file_path):
            candidate = hasher.copy()
            has_content = False
            for chunk in chunks:
                candidate.update(chunk)
                has_content = True
            # Empty content would leave a non-empty file with blank hashes,
            # which an incremental scan reads as changed every time.
            fed = candidate if has_content else None
    except ArchiveReadError as e:
        log.warning(f"{e}. Hashing the file itself instead.")
        return None
    return fed


def _iter_chunks(
    reader: IO[bytes] | io.BufferedIOBase,
    file_path: Path,
    name: str,
    deadline: float,
) -> Iterator[bytes]:
    """Stream a member's bytes, raising `ArchiveReadError` if it can't be read
    or `deadline` passes.

    Chunks are consumed by the caller, outside the reader's own error
    handling, so decompression failures (a bad CRC, truncated data) surface
    here rather than escaping as a raw zipfile/tarfile error.
    """
    try:
        while chunk := reader.read(FILE_READ_CHUNK_SIZE):
            yield chunk
            _check_deadline(deadline, file_path)
    except (
        zipfile.BadZipFile,
        tarfile.TarError,
        zlib.error,
        lzma.LZMAError,
        EOFError,
        OSError,
        # inflate64 reports a corrupt Deflate64 stream as a ValueError.
        ValueError,
    ) as e:
        raise ArchiveReadError(f"Error reading {name} from {file_path}: {e}") from e


def _eligible_zip_entries(
    z: zipfile.ZipFile, excluded_names: list[str], excluded_exts: list[str]
) -> list[zipfile.ZipInfo]:
    return [
        entry
        for entry in sorted(z.infolist(), key=lambda e: e.filename)
        if not entry.is_dir()
        and not _is_member_excluded(entry.filename, excluded_names, excluded_exts)
    ]


def _undecodable_zip_method(
    z: zipfile.ZipFile, entries: list[zipfile.ZipInfo]
) -> int | None:
    """Opening an entry reads only its local header, so probing every member
    is cheap and tracks whatever this Python and the inflate64 patch decode."""
    for entry in entries:
        try:
            z.open(entry, "r").close()
        except NotImplementedError:
            return entry.compress_type
    return None


def read_zip_archive_files(
    file_path: Path,
    excluded_names: list[str],
    excluded_exts: list[str],
) -> Iterator[tuple[str, int, Iterator[bytes]]]:
    """Yield eligible zip entries in ASCII path order.

    Each yielded `(internal_name, file_size_bytes, chunks)` streams its
    member's bytes lazily; chunks must be fully consumed before advancing
    to the next entry, since the underlying file is closed at that point.

    An archive with a method zipfile can't decode goes through 7zz as a whole,
    so a stored .cue next to a PPMd .bin is never streamed twice.

    Raises `ArchiveReadError` if the archive can't be read in full, so callers
    never mistake a partial read for a complete one.
    """
    deadline = _read_deadline()
    try:
        with zipfile.ZipFile(file_path, "r") as z:
            entries = _eligible_zip_entries(z, excluded_names, excluded_exts)
            undecodable_method = _undecodable_zip_method(z, entries)
            if undecodable_method is None:
                for entry in entries:
                    name = entry.filename
                    with z.open(entry, "r") as f:
                        yield name, entry.file_size, _iter_chunks(
                            f, file_path, name, deadline
                        )
                return
    except (zipfile.BadZipFile, RuntimeError, OSError, ValueError) as e:
        raise ArchiveReadError(f"Error reading zip {file_path}: {e}") from e

    log.debug(
        f"Zip {file_path} uses compression method {undecodable_method}, which "
        "zipfile can't decode; reading it through 7zz"
    )
    yield from read_7z_archive_files(file_path, excluded_names, excluded_exts)


def read_tar_archive_files(
    file_path: Path,
    excluded_names: list[str],
    excluded_exts: list[str],
) -> Iterator[tuple[str, int, Iterator[bytes]]]:
    """Yield eligible tar entries (.tar/.tar.gz/.tar.bz2/.tar.xz) in ASCII path order.

    Each yielded `(internal_name, file_size_bytes, chunks)` streams its
    member's bytes lazily; chunks must be fully consumed before advancing
    to the next entry, since the underlying file is closed at that point.

    Raises `ArchiveReadError` if the archive can't be read in full, so callers
    never mistake a partial read for a complete one.
    """
    deadline = _read_deadline()
    try:
        with tarfile.open(file_path, "r:*") as tf:
            members = sorted(
                (m for m in tf.getmembers() if m.isfile()),
                key=lambda m: m.name,
            )
            for member in members:
                name = member.name
                base_name = Path(name).name
                lower = base_name.lower()

                if any(lower.endswith("." + ext) for ext in excluded_exts):
                    continue

                if any(
                    base_name == exc or fnmatch.fnmatch(base_name, exc)
                    for exc in excluded_names
                ):
                    continue

                ef = tf.extractfile(member)
                if ef is None:
                    continue

                with ef:
                    yield member.name, member.size, _iter_chunks(
                        ef, file_path, name, deadline
                    )
    except (tarfile.TarError, OSError) as e:
        raise ArchiveReadError(f"Error reading tar {file_path}: {e}") from e


def _stream_7z_chunks(
    process: subprocess.Popen[bytes],
    deadline: float,
    on_timeout: Callable[[], None],
) -> Iterator[bytes]:
    assert process.stdout is not None
    while chunk := process.stdout.read(FILE_READ_CHUNK_SIZE):
        if time.monotonic() > deadline:
            process.terminate()
            on_timeout()
            return
        yield chunk


def _is_member_excluded(
    member: str,
    excluded_names: list[str],
    excluded_exts: list[str],
) -> bool:
    base_name = Path(member).name
    lower = base_name.lower()
    if any(lower.endswith("." + ext) for ext in excluded_exts):
        return True
    return any(
        base_name == exc or fnmatch.fnmatch(base_name, exc) for exc in excluded_names
    )


def _stream_archive_members(
    file_path: Path,
    entries: list[tuple[str, int]],
) -> Iterator[tuple[str, int, Iterator[bytes]]]:
    """Stream each listed member of an archive, one subprocess at a time.

    Members are yielded in ASCII path order under a single time budget shared
    by the whole archive. Raises `ArchiveReadError` if any member fails or the
    budget is spent, so callers never mistake a partial read for a complete one.
    """
    entries = sorted(entries, key=lambda e: e[0])

    deadline = time.monotonic() + SEVEN_ZIP_TIMEOUT
    timed_out = False

    def _mark_timed_out() -> None:
        nonlocal timed_out
        timed_out = True

    for name, size in entries:
        # Once the shared budget is spent, stop spawning a subprocess per
        # remaining member; otherwise each one trips the deadline and spams
        # an identical error line for every entry left in the archive.
        if timed_out or time.monotonic() > deadline:
            timed_out = True
            break
        try:
            with subprocess.Popen(
                _archive_member_command(file_path, name),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                shell=False,  # trunk-ignore(bandit/B603)
            ) as process:
                if process.stdout is None:
                    continue
                with _kill_at_deadline(process, deadline) as expired:
                    yield name, size, _stream_7z_chunks(
                        process, deadline, _mark_timed_out
                    )
                if expired.is_set():
                    _mark_timed_out()
            # A timeout terminates the subprocess, so a non-zero return code is
            # expected then and is covered by the single raise below.
            if not timed_out and process.returncode != 0:
                raise ArchiveReadError(
                    f"Extraction of {name} from {file_path} failed "
                    f"with code {process.returncode}"
                )
        except (OSError, ValueError) as e:
            raise ArchiveReadError(
                f"Error extracting {name} from {file_path}: {e}"
            ) from e

    if timed_out:
        raise ArchiveReadError(
            f"Extraction timed out after {SEVEN_ZIP_TIMEOUT}s reading members of "
            f"{file_path}; raise SEVEN_ZIP_TIMEOUT for large archives"
        )


def read_7z_archive_files(
    file_path: Path,
    excluded_names: list[str],
    excluded_exts: list[str],
) -> Iterator[tuple[str, int, Iterator[bytes]]]:
    """Yield eligible files from a 7z archive in ASCII path order.

    Each yielded `(internal_name, file_size_bytes, chunks)` streams its
    member's bytes lazily; chunks must be fully consumed before advancing
    to the next entry, since the underlying subprocess is reaped at that point.

    Raises `ArchiveReadError` if any member cannot be read in full.
    """
    entries = [
        (name, size)
        for name, size in _list_archive_file_members(file_path)
        if not _is_member_excluded(name, excluded_names, excluded_exts)
    ]
    yield from _stream_archive_members(file_path, entries)


def read_rar_archive_files(
    file_path: Path,
    excluded_names: list[str],
    excluded_exts: list[str],
) -> Iterator[tuple[str, int, Iterator[bytes]]]:
    """Yield eligible files from a RAR archive in ASCII path order.

    Same contract as `read_7z_archive_files`, but listing and extraction go
    through bsdtar since the bundled 7zz has no RAR codec.
    """
    entries = [
        (name, size)
        for name, size in _list_rar_file_members(file_path)
        if not _is_member_excluded(name, excluded_names, excluded_exts)
    ]
    yield from _stream_archive_members(file_path, entries)


def _is_rar_archive(file_path: Path) -> bool:
    return str(file_path).lower().endswith(RAR_FILE_EXTENSIONS)


def _bsdtar_member_pattern(member: str) -> str:
    """Escape a member name so bsdtar matches it literally.

    Without this, a stored name containing `*` or `?` is a glob that can
    select (and concatenate) other members of the same archive.
    """
    return "".join(
        f"\\{char}" if char in _BSDTAR_GLOB_METACHARACTERS else char for char in member
    )


def _unescape_mtree_path(raw: bytes) -> str:
    unescaped = _MTREE_OCTAL_ESCAPE.sub(lambda m: bytes([int(m.group(1), 8)]), raw)
    # surrogateescape round-trips names that aren't valid UTF-8, so they still
    # encode back to the original bytes when passed to bsdtar.
    return unescaped.decode("utf-8", errors="surrogateescape")


def _list_rar_file_members(file_path: Path) -> list[tuple[str, int]]:
    """List `(member_path, size)` for every file member of a RAR archive.

    Rewriting the archive as an mtree listing on stdout is libarchive's only
    machine-readable listing; `bsdtar -tv` output is ls-style and ambiguous
    for names containing spaces. Only headers are read, so listing stays cheap
    regardless of archive size.
    """
    try:
        result = subprocess.run(
            [
                BSDTAR_PATH,
                "-cf",
                "-",
                "--format=mtree",
                "--options=!all,type,size",
                f"@{file_path}",
            ],
            capture_output=True,
            check=True,
            timeout=SEVEN_ZIP_TIMEOUT,
            shell=False,  # trunk-ignore(bandit/B603): bsdtar path is hardcoded, args are validated
        )
    except (
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
        FileNotFoundError,
    ) as e:
        log.error(f"Error listing RAR archive {file_path}: {e}")
        return []

    entries: list[tuple[str, int]] = []
    for line in result.stdout.splitlines():
        # "#" starts a comment, "/" an mtree directive; neither is an entry.
        if not line or line.startswith((b"#", b"/")):
            continue
        raw_path, _, keywords = line.partition(b" ")
        fields = dict(
            field.split(b"=", 1) for field in keywords.split() if b"=" in field
        )
        if fields.get(b"type") != b"file":
            continue
        try:
            size = int(fields.get(b"size", b"0"))
        except ValueError:
            size = 0
        # mtree paths are archive-root relative ("./game.gba"), stored member
        # names are not.
        name = _unescape_mtree_path(raw_path).removeprefix("./")
        if name:
            entries.append((name, size))

    return entries


def _archive_member_command(file_path: Path, member: str) -> list[str]:
    """Build the command streaming a single archive member to stdout."""
    if _is_rar_archive(file_path):
        return [
            BSDTAR_PATH,
            "-xOf",
            str(file_path),
            "--",
            _bsdtar_member_pattern(member),
        ]

    # "-spd" disables wildcard matching so a member name containing "*" or "?"
    # can't select other members; "--" stops switch parsing so one starting
    # with "-" or "@" stays a member name.
    return [SEVEN_ZIP_PATH, "e", str(file_path), "-so", "-y", "-spd", "--", member]


def _list_archive_file_members(file_path: Path) -> list[tuple[str, int]]:
    """List `(member_path, size)` for every file member via `7zz l -slt -ba`.

    Single-stream formats (.gz/.xz) list no `Attributes` line at all, so an
    entry is committed when the next `Path =` starts or the listing ends,
    and only dropped when its attributes mark it as a directory.
    """
    if _is_rar_archive(file_path):
        return _list_rar_file_members(file_path)

    try:
        result = subprocess.run(
            [SEVEN_ZIP_PATH, "l", "-slt", "-ba", str(file_path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=SEVEN_ZIP_TIMEOUT,
            shell=False,  # trunk-ignore(bandit/B603): 7z path is hardcoded, args are validated
        )
    except (
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
        FileNotFoundError,
    ) as e:
        log.error(f"Error listing archive {file_path}: {e}")
        return []

    entries: list[tuple[str, int]] = []
    current_file: str | None = None
    current_size = 0
    current_is_dir = False

    def _commit() -> None:
        if current_file and not current_is_dir:
            entries.append((current_file, current_size))

    for line in result.stdout.split("\n"):
        line = line.lstrip()
        if line.startswith("Path = "):
            _commit()
            current_file = line.split(" = ", 1)[1]
            current_size = 0
            current_is_dir = False
        elif line.startswith("Size = "):
            try:
                current_size = int(line.split(" = ")[1].strip())
            except ValueError:
                current_size = 0
        elif line.startswith("Attributes = "):
            current_is_dir = line.split(" = ")[1].strip().startswith("D")
    _commit()

    return entries


def _extract_member_to_dir(
    file_path: Path, member: str, dest_dir: Path, deadline: float
) -> Path | None:
    """Stream one archive member into `dest_dir`, named after its basename.

    Returns None (leaving no partial file) when extraction fails or exceeds
    the deadline.
    """
    dest_path = dest_dir / Path(member).name
    try:
        # stderr goes to an unlinked temp file rather than a pipe: a pipe can
        # fill and block the extractor while this thread waits on stdout,
        # stalling past the deadline.
        with tempfile.TemporaryFile() as stderr_file:
            with (
                open(dest_path, "wb") as dest_file,
                subprocess.Popen(
                    _archive_member_command(file_path, member),
                    stdout=subprocess.PIPE,
                    stderr=stderr_file,
                    shell=False,  # trunk-ignore(bandit/B603): binary paths are hardcoded, args are validated
                ) as process,
                _kill_at_deadline(process, deadline) as expired,
            ):
                assert process.stdout is not None
                while chunk := process.stdout.read(FILE_READ_CHUNK_SIZE):
                    if time.monotonic() > deadline:
                        process.terminate()
                        expired.set()
                        break
                    dest_file.write(chunk)

            if expired.is_set():
                log.error(
                    f"Extraction of {member} from {file_path} timed out "
                    f"after {SEVEN_ZIP_TIMEOUT}s; raise SEVEN_ZIP_TIMEOUT "
                    "for large archives"
                )
                dest_path.unlink(missing_ok=True)
                return None

            if process.returncode != 0:
                # Surface the extractor's own reason (e.g. "Unsupported
                # Method") so scan logs explain the missing hash.
                stderr_file.seek(0)
                detail = stderr_file.read().decode(errors="replace").strip()
                log.error(
                    f"Extraction of {member} from {file_path} failed "
                    f"with code {process.returncode}: {detail or 'no error output'}"
                )
                dest_path.unlink(missing_ok=True)
                return None

        return dest_path
    except OSError as e:
        log.error(f"Error extracting {member} from {file_path}: {e}")
        dest_path.unlink(missing_ok=True)
        return None


def extract_largest_archive_member(file_path: Path, dest_dir: Path) -> Path | None:
    """Extract an archive's largest file member into `dest_dir` via 7zz.

    Compressed tarballs (.tgz/.tbz2/.txz) list only their inner .tar, so one
    nested extraction pass unwraps it; deeper nesting gives up. Returns the
    extracted file's path, or None on any failure (no partial files remain).
    """
    deadline = time.monotonic() + SEVEN_ZIP_TIMEOUT
    source = file_path

    for _ in range(2):
        members = _list_archive_file_members(source)
        extracted = (
            _extract_member_to_dir(
                source, max(members, key=lambda m: m[1])[0], dest_dir, deadline
            )
            if members
            else None
        )
        if source != file_path:
            source.unlink(missing_ok=True)
        if extracted is None:
            return None
        if not str(extracted).lower().endswith(tuple(COMPRESSED_FILE_EXTENSIONS)):
            return extracted
        source = extracted

    log.error(f"Archive {file_path} is nested too deeply to extract")
    source.unlink(missing_ok=True)
    return None


def is_chd_file(file_path: Path, mime_type: str | None = None) -> bool:
    """Return True if the file is a CHD by extension or libmagic MIME type.

    Args:
        mime_type: The file's libmagic MIME type, detected here when not given.
    """
    if file_path.suffix.lower() == ".chd":
        return True
    if mime_type is None:
        mime_type = detect_mime_type(file_path)
    return mime_type == CHD_MIME_TYPE


def extract_chd_hash(file_path: Path) -> str:
    """
    Extract the embedded SHA1 hash from a CHD (Compressed Hunks of Data) v5 file header.

    Only CHD v5 files are supported, matching MAMERedump's database.

    CHD v5 files store the combined raw+meta SHA1 hash in the header.
    This hash is what ROM databases use for CHD identification, since it includes
    metadata like CD track layouts which are essential for proper disc image
    identification.

    For reference, check out "chd.h" in the MAME source tree.

    ---------------------------------- Why? ----------------------------------
    CHDMAN does not produce nor guarantee stable, byte-for-byte identical
    outputs for a given disc image. (Including HD images.)

    For this reason, the CHD format embeds the original source data hash in
    its header, allowing different CHD files to be verified as equivalent
    even when their compressed representations differ.
    --------------------------------------------------------------------------

    Args:
        file_path: Path to the CHD file

    Returns:
        The embedded SHA1 hash as a hex string for a valid CHD v5 file, or an
        empty string if the file is invalid, uses an unsupported CHD version,
        is truncated, or cannot be read due to an I/O error.
    """
    try:
        with open(file_path, "rb") as f:
            # Read the v5 header and extract the embedded SHA1
            header = f.read(CHD_V5_HEADER_LENGTH)

            # Check for "MComprHD" signature
            if (
                len(header) < CHD_MIN_HEADER_LENGTH
                or header[:CHD_SIGNATURE_LENGTH] != CHD_SIGNATURE
            ):
                return ""

            # Extract and verify version (big-endian uint32)
            version_end = CHD_VERSION_OFFSET + CHD_VERSION_LENGTH
            version = int.from_bytes(header[CHD_VERSION_OFFSET:version_end], "big")

            # Only support v5 CHD files
            if version != CHD_V5_VERSION:
                return ""

            # Extract combined raw+meta SHA1 from v5 header
            sha1_end = CHD_V5_SHA1_OFFSET + CHD_V5_SHA1_LENGTH
            if len(header) < sha1_end:
                return ""
            sha1_bytes = header[CHD_V5_SHA1_OFFSET:sha1_end]
            return sha1_bytes.hex()
    except OSError:
        return ""
