import os
import re
from collections.abc import Iterator
from pathlib import Path


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


INVALID_CHARS_HYPHENS = re.compile(r"[\\/:|]")
INVALUD_CHARS_EMPTY = re.compile(r'[*?"<>]')


def sanitize_filename(filename):
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
    sanitized_filename = INVALUD_CHARS_EMPTY.sub("", sanitized_filename)

    # Ensure null bytes are not included (ZFS allows any characters except null bytes)
    sanitized_filename = sanitized_filename.replace("\0", "")

    # Remove leading/trailing whitespace
    sanitized_filename = sanitized_filename.strip()

    # Ensure the filename is not empty
    if not sanitized_filename:
        raise ValueError("Filename cannot be empty after sanitization")

    return sanitized_filename
