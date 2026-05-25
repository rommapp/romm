# trunk-ignore-all(bandit/B404)

import subprocess
import time
from collections.abc import Callable, Iterator
from pathlib import Path

from config import SEVEN_ZIP_TIMEOUT
from logger.logger import log

SEVEN_ZIP_PATH = "/usr/bin/7zz"
FILE_READ_CHUNK_SIZE = 1024 * 8


class SevenZipExtractError(Exception):
    """Raised when a 7z entry could not be extracted cleanly (timeout, bad exit, OS error)."""


def _list_7z_entries(file_path: Path) -> list[tuple[str, int]]:
    """Return [(internal_name, size_bytes)] for every file (not dir) in a 7z archive."""
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
        log.error(f"Error listing 7z archive {file_path}: {e}")
        return []

    entries: list[tuple[str, int]] = []
    name: str | None = None
    size = 0
    for line in result.stdout.split("\n"):
        line = line.lstrip()
        if line.startswith("Path = "):
            name = line.split(" = ", 1)[1]
        elif line.startswith("Size = "):
            try:
                size = int(line.split(" = ", 1)[1].strip())
            except ValueError:
                size = 0
        elif line.startswith("Attributes = "):
            attrs = line.split(" = ", 1)[1].strip()
            if name and not attrs.startswith("D"):
                entries.append((name, size))
            name, size = None, 0
    return entries


def process_file_7z(
    file_path: Path,
    fn_hash_update: Callable[[bytes | bytearray], None],
) -> bool:
    """
    Process a 7zip file using the system's 7zip binary and use the provided callables to update the calculated hashes.

    Args:
        file_path: Path to the 7z file
        fn_hash_update: Callback to update hashes with data chunks
    """

    entries = _list_7z_entries(file_path)
    if not entries:
        return False

    largest_file, _ = max(entries, key=lambda e: e[1])
    log.debug(f"Extracting {largest_file} from {file_path}...")

    try:
        for chunk in _stream_7z_entry(
            file_path, largest_file, time.monotonic() + SEVEN_ZIP_TIMEOUT
        ):
            fn_hash_update(chunk)
        return True
    except SevenZipExtractError as e:
        log.error(f"7z extraction failed: {e}")
        return False


def _stream_7z_entry(
    file_path: Path, entry_name: str, deadline: float
) -> Iterator[bytes]:
    """Yield chunks of a single 7z entry; raises SevenZipExtractError on failure."""
    try:
        process = subprocess.Popen(
            [SEVEN_ZIP_PATH, "e", str(file_path), entry_name, "-so", "-y"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,  # trunk-ignore(bandit/B603): 7z path is hardcoded, args are validated
        )
    except (OSError, ValueError) as e:
        raise SevenZipExtractError(str(e)) from e

    with process:
        assert process.stdout is not None
        while chunk := process.stdout.read(FILE_READ_CHUNK_SIZE):
            if time.monotonic() > deadline:
                process.terminate()
                raise SevenZipExtractError(f"7z extraction of {entry_name} timed out")
            yield chunk

    if process.returncode != 0:
        raise SevenZipExtractError(
            f"7z extraction of {entry_name} failed with code {process.returncode}"
        )


def iter_7z_archive_files(
    file_path: Path,
) -> Iterator[tuple[str, int, Iterator[bytes]]]:
    """Yield (name, size, chunk_iter) for every file in a 7z archive, in ASCII name order.

    Consumers should catch :class:`SevenZipExtractError` raised mid-iteration.
    """
    deadline = time.monotonic() + SEVEN_ZIP_TIMEOUT
    for name, size in sorted(_list_7z_entries(file_path)):
        yield name, size, _stream_7z_entry(file_path, name, deadline)
