import os
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
