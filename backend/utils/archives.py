# trunk-ignore-all(bandit/B404)

import bz2
import fnmatch
import os
import re
import subprocess
import tarfile
import tempfile
import threading
import time
import zipfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import IO, Final, Literal

import magic
import zipfile_inflate64  # trunk-ignore(ruff/F401): Patches zipfile to support Enhanced Deflate

from config import SEVEN_ZIP_TIMEOUT
from logger.logger import log
from utils.filesystem import COMPRESSED_FILE_EXTENSIONS

SEVEN_ZIP_PATH = "/usr/bin/7zz"
# The bundled 7zz is built without the RAR codec (it is under the restrictive
# unRAR license), so RAR archives are read through libarchive's bsdtar instead.
BSDTAR_PATH = "/usr/bin/bsdtar"

RAR_FILE_EXTENSIONS: Final = (".rar",)

# libarchive escapes the backslash and every byte outside printable ASCII as a
# 3-digit octal sequence in the mtree listings we parse RAR members from.
_MTREE_OCTAL_ESCAPE: Final = re.compile(rb"\\([0-7]{3})")

# bsdtar treats member arguments as glob patterns, where a backslash escapes
# the character that follows it.
_BSDTAR_GLOB_METACHARACTERS: Final = frozenset("\\*?[]")

# Known compressed file MIME types
COMPRESSED_MIME_TYPES: Final = frozenset(
    (
        "application/x-7z-compressed",
        "application/x-bzip2",
        "application/x-gzip",
        "application/x-tar",
        "application/zip",
    )
)

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

FILE_READ_CHUNK_SIZE = 1024 * 8
_MIME_DETECTOR = magic.Magic(mime=True)
_MIME_DETECTOR_LOCK = threading.Lock()


class ArchiveReadError(Exception):
    """An archive's members could not be fully read."""


def detect_mime_type(file_path: os.PathLike[str] | str) -> str:
    """Detect MIME type via libmagic; returns empty string on error."""
    try:
        with _MIME_DETECTOR_LOCK:
            return _MIME_DETECTOR.from_file(file_path)
    except (OSError, magic.MagicException):
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


def read_zip_file(file: str | os.PathLike[str] | IO[bytes]) -> Iterator[bytes]:
    try:
        with zipfile.ZipFile(file, "r") as z:
            # Find the biggest file in the archive
            largest_file = max(z.infolist(), key=lambda x: x.file_size)
            with z.open(largest_file, "r") as f:
                while chunk := f.read(FILE_READ_CHUNK_SIZE):
                    yield chunk
    except (zipfile.BadZipFile, RuntimeError, OSError):
        if isinstance(file, Path):
            for chunk in read_basic_file(file):
                yield chunk


def read_tar_file(
    file_path: Path, mode: Literal["r", "r:*", "r:", "r:gz", "r:bz2", "r:xz"] = "r"
) -> Iterator[bytes]:
    try:
        with tarfile.open(file_path, mode) as f:
            regular_files = [member for member in f.getmembers() if member.isfile()]

            # Find the largest file among regular files only
            largest_file = max(regular_files, key=lambda x: x.size)
            with f.extractfile(largest_file) as ef:  # type: ignore
                with ef:
                    while chunk := ef.read(FILE_READ_CHUNK_SIZE):
                        yield chunk
    except tarfile.ReadError:
        for chunk in read_basic_file(file_path):
            yield chunk


def read_gz_file(file_path: Path) -> Iterator[bytes]:
    return read_tar_file(file_path, "r:gz")


def _process_largest_7z_member(
    file_path: Path,
    fn_hash_update: Callable[[bytes | bytearray], None],
) -> bool:
    """Stream the largest member of a 7z archive through `fn_hash_update`.

    Returns True on success, False if listing/extraction fails or times out.
    """
    try:
        result = subprocess.run(
            [SEVEN_ZIP_PATH, "l", "-slt", "-ba", str(file_path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=SEVEN_ZIP_TIMEOUT,
            shell=False,  # trunk-ignore(bandit/B603): 7z path is hardcoded, args are validated
        )

        largest_file = None
        largest_size = 0
        current_file = None
        current_size = 0

        for line in result.stdout.split("\n"):
            line = line.lstrip()
            if line.startswith("Path = "):
                current_file = line.split(" = ", 1)[1]
            elif line.startswith("Size = "):
                try:
                    current_size = int(line.split(" = ")[1].strip())
                except ValueError:
                    current_size = 0
            elif line.startswith("Attributes = "):
                attrs = line.split(" = ")[1].strip()
                if current_file and not attrs.startswith("D"):
                    if current_size > largest_size:
                        largest_size = current_size
                        largest_file = current_file

        if not largest_file:
            return False

        log.debug(f"Extracting {largest_file} from {file_path}...")

        start_decompression_time = time.monotonic()

        with subprocess.Popen(
            [SEVEN_ZIP_PATH, "e", str(file_path), largest_file, "-so", "-y", "-spd"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,  # trunk-ignore(bandit/B603): 7z path is hardcoded, args are validated
        ) as process:
            if process.stdout:
                while chunk := process.stdout.read(FILE_READ_CHUNK_SIZE):
                    if time.monotonic() - start_decompression_time > SEVEN_ZIP_TIMEOUT:
                        process.terminate()
                        log.error("7z extraction timed out")
                        return False
                    fn_hash_update(chunk)

        if process.returncode != 0:
            log.error(f"7z extraction failed with return code {process.returncode}")
            return False

        return True

    except (
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
        FileNotFoundError,
    ) as e:
        log.error(f"Error processing 7z file: {e}")
        return False


def process_7z_file(
    file_path: Path,
    fn_hash_update: Callable[[bytes | bytearray], None],
) -> None:
    if not _process_largest_7z_member(file_path, fn_hash_update):
        for chunk in read_basic_file(file_path):
            fn_hash_update(chunk)


def read_bz2_file(file_path: Path) -> Iterator[bytes]:
    try:
        with bz2.BZ2File(file_path, "rb") as f:
            while chunk := f.read(FILE_READ_CHUNK_SIZE):
                yield chunk
    except EOFError:
        for chunk in read_basic_file(file_path):
            yield chunk


def _iter_chunks(reader: IO[bytes]) -> Iterator[bytes]:
    while chunk := reader.read(FILE_READ_CHUNK_SIZE):
        yield chunk


def read_zip_archive_files(
    file_path: Path,
    excluded_names: list[str],
    excluded_exts: list[str],
) -> Iterator[tuple[str, int, Iterator[bytes]]]:
    """Yield eligible zip entries in ASCII path order.

    Each yielded `(internal_name, file_size_bytes, chunks)` streams its
    member's bytes lazily; chunks must be fully consumed before advancing
    to the next entry, since the underlying file is closed at that point.
    """
    try:
        with zipfile.ZipFile(file_path, "r") as z:
            entries = sorted(z.infolist(), key=lambda e: e.filename)
            for entry in entries:
                if entry.is_dir():
                    continue
                name = entry.filename
                base_name = Path(name).name
                lower = base_name.lower()
                if any(lower.endswith("." + ext) for ext in excluded_exts):
                    continue
                if any(
                    base_name == exc or fnmatch.fnmatch(base_name, exc)
                    for exc in excluded_names
                ):
                    continue
                with z.open(entry, "r") as f:
                    yield name, entry.file_size, _iter_chunks(f)
    except (zipfile.BadZipFile, RuntimeError, OSError):
        return


def read_tar_archive_files(
    file_path: Path,
    excluded_names: list[str],
    excluded_exts: list[str],
) -> Iterator[tuple[str, int, Iterator[bytes]]]:
    """Yield eligible tar entries (.tar/.tar.gz/.tar.bz2/.tar.xz) in ASCII path order.

    Each yielded `(internal_name, file_size_bytes, chunks)` streams its
    member's bytes lazily; chunks must be fully consumed before advancing
    to the next entry, since the underlying file is closed at that point.
    """
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
                    yield member.name, member.size, _iter_chunks(ef)
    except tarfile.ReadError:
        return


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
                yield name, size, _stream_7z_chunks(process, deadline, _mark_timed_out)
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
        raise ArchiveReadError(f"Extraction timed out reading members of {file_path}")


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
        return [BSDTAR_PATH, "-xOf", str(file_path), _bsdtar_member_pattern(member)]

    # "-spd" disables wildcard matching so a member name containing "*" or "?"
    # can't select (and concatenate) other members.
    return [SEVEN_ZIP_PATH, "e", str(file_path), member, "-so", "-y", "-spd"]


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
            ):
                assert process.stdout is not None
                while chunk := process.stdout.read(FILE_READ_CHUNK_SIZE):
                    if time.monotonic() > deadline:
                        process.terminate()
                        log.error(f"Extraction of {member} from {file_path} timed out")
                        dest_path.unlink(missing_ok=True)
                        return None
                    dest_file.write(chunk)

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


def is_chd_file(file_path: Path) -> bool:
    """Return True if the file is a CHD by extension or libmagic-detected MIME type."""
    if file_path.suffix.lower() == ".chd":
        return True

    try:
        with _MIME_DETECTOR_LOCK:
            return _MIME_DETECTOR.from_file(file_path) == CHD_MIME_TYPE
    except (OSError, magic.MagicException):
        return False


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
