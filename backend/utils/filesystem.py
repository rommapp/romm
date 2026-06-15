import errno
import os
import re
import shutil
from collections.abc import Iterator
from pathlib import Path

# Container file extensions treated as compressed archives across modules
# (roms_handler for hashing decisions, rahasher for skipping disc-platform
# buffer-hash attempts, feeds for PKGi passthrough).
COMPRESSED_FILE_EXTENSIONS: frozenset[str] = frozenset(
    (".7z", ".bz2", ".gz", ".rar", ".tar", ".zip", ".xz", ".tgz", ".tbz2", ".txz")
)


def iter_files(path: str, recursive: bool = False) -> Iterator[tuple[Path, str]]:
    """List files in a directory.

    Yields tuples where the first element is the path to the directory where the file is located,
    and the second element is the name of the file.
    """
    for root, _, files in os.walk(path, topdown=True):
        for file in files:
            yield Path(root), file
        if not recursive:
            break


def iter_directories(path: str, recursive: bool = False) -> Iterator[tuple[Path, str]]:
    """List directories in a directory.

    Yields tuples where the first element is the path to the directory where the directory is located,
    and the second element is the name of the directory.
    """
    for root, dirs, _ in os.walk(path, topdown=True):
        for directory in dirs:
            yield Path(root), directory
        if not recursive:
            break


# errno values that mean "hardlink not possible here, fall back to copy".
# EXDEV: cross-device link. EPERM: filesystem doesn't permit/support hardlinks
# (e.g. FAT32, exFAT, some network mounts). EOPNOTSUPP/ENOTSUP: same, on BSD/macOS.
# EMLINK: source already has the maximum number of hardlinks for the filesystem.
_LINK_FALLBACK_ERRNOS: frozenset[int] = frozenset(
    e
    for e in (
        getattr(errno, "EXDEV", None),
        getattr(errno, "EPERM", None),
        getattr(errno, "EOPNOTSUPP", None),
        getattr(errno, "ENOTSUP", None),
        getattr(errno, "EMLINK", None),
        getattr(errno, "EACCES", None),
    )
    if e is not None
)


def link_or_copy_file(source: Path, dest: Path) -> None:
    """Place ``source`` at ``dest`` via hardlink (preferred) or copy (fallback),
    atomically replacing ``dest`` if it already exists. Caller is responsible
    for creating ``dest.parent``.

    Hardlinking is preferred because it's instantaneous and uses no extra disk
    space, but only works within a single filesystem. If linking isn't possible,
    we transparently fall back to ``shutil.copy2`` (preserving metadata).

    Overwriting is atomic: we link/copy to a tempfile in dest's directory, then
    rename it onto dest, which mirrors shutil.copy2's overwrite-on-exists
    behavior.
    """
    tmp_path = dest.parent / f".romm_link_tmp_{os.urandom(8).hex()}"
    try:
        try:
            os.link(source, tmp_path)
        except OSError as exc:
            if exc.errno not in _LINK_FALLBACK_ERRNOS:
                raise
            shutil.copy2(source, tmp_path)
        os.replace(tmp_path, dest)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


INVALID_CHARS_HYPHENS = re.compile(r"[\\/:|]")
INVALID_CHARS_EMPTY = re.compile(r'[*?"<>+]')


def sanitize_filename(filename: str) -> str:
    """
    Replace invalid characters in the filename to make it valid across common filesystems

    Args:
    - filename (str): The filename to sanitize.

    Returns:
    - str: The sanitized filename.
    """
    # Replace some invalid characters with hyphen
    sanitized_filename = INVALID_CHARS_HYPHENS.sub("-", filename)

    # Remove other invalid characters
    sanitized_filename = INVALID_CHARS_EMPTY.sub("", sanitized_filename)

    # Ensure null bytes are not included (ZFS allows any characters except null bytes)
    sanitized_filename = sanitized_filename.replace("\0", "")

    # Remove leading/trailing whitespace
    sanitized_filename = sanitized_filename.strip()

    # Ensure the filename is not empty
    if not sanitized_filename:
        raise ValueError("Filename cannot be empty after sanitization")

    return sanitized_filename
