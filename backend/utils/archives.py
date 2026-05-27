import bz2
import fnmatch
import os
import tarfile
import threading
import zipfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import IO, Final, Literal

import magic
import zipfile_inflate64  # trunk-ignore(ruff/F401): Patches zipfile to support Enhanced Deflate

from utils.archive_7zip import process_file_7z
from utils.filesystem import COMPRESSED_FILE_EXTENSIONS

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


def detect_mime_type(file_path: os.PathLike[str] | str) -> str:
    """Detect MIME type via libmagic; returns empty string on error."""
    try:
        with _MIME_DETECTOR_LOCK:
            return _MIME_DETECTOR.from_file(file_path)
    except magic.MagicException:
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
    except zipfile.BadZipFile:
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
                while chunk := ef.read(FILE_READ_CHUNK_SIZE):
                    yield chunk
    except tarfile.ReadError:
        for chunk in read_basic_file(file_path):
            yield chunk


def read_gz_file(file_path: Path) -> Iterator[bytes]:
    return read_tar_file(file_path, "r:gz")


def process_7z_file(
    file_path: Path,
    fn_hash_update: Callable[[bytes | bytearray], None],
) -> None:
    processed = process_file_7z(
        file_path=file_path,
        fn_hash_update=fn_hash_update,
    )
    if not processed:
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


def read_zip_archive_files(
    file_path: Path,
    excluded_names: list[str],
    excluded_exts: list[str],
) -> list[tuple[str, int, list[bytes]]]:
    """Read all eligible zip entries in ASCII path order.

    Returns [(internal_name, file_size_bytes, chunks)] or [] on error.
    """
    results: list[tuple[str, int, list[bytes]]] = []
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
                chunks: list[bytes] = []
                with z.open(entry, "r") as f:
                    while chunk := f.read(FILE_READ_CHUNK_SIZE):
                        chunks.append(chunk)
                results.append((name, entry.file_size, chunks))
    except zipfile.BadZipFile:
        pass
    return results


def read_tar_archive_files(
    file_path: Path,
    excluded_names: list[str],
    excluded_exts: list[str],
) -> list[tuple[str, int, list[bytes]]]:
    """Read all eligible tar entries (handles .tar/.tar.gz/.tar.bz2/.tar.xz) in ASCII path order.

    Returns [(internal_name, file_size_bytes, chunks)] or [] on error.
    """
    results: list[tuple[str, int, list[bytes]]] = []
    try:
        with tarfile.open(file_path, "r") as tf:
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
                chunks: list[bytes] = []
                while chunk := ef.read(FILE_READ_CHUNK_SIZE):
                    chunks.append(chunk)
                results.append((name, member.size, chunks))
    except tarfile.ReadError:
        pass
    return results


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
