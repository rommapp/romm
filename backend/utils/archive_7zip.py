# trunk-ignore-all(bandit/B404)

import fnmatch
import subprocess
import time
from collections.abc import Callable, Iterator
from pathlib import Path

from config import SEVEN_ZIP_TIMEOUT
from logger.logger import log

SEVEN_ZIP_PATH = "/usr/bin/7zz"
FILE_READ_CHUNK_SIZE = 1024 * 8


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

    try:
        result = subprocess.run(
            [SEVEN_ZIP_PATH, "l", "-slt", "-ba", str(file_path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=SEVEN_ZIP_TIMEOUT,
            shell=False,  # trunk-ignore(bandit/B603): 7z path is hardcoded, args are validated
        )

        lines = result.stdout.split("\n")

        largest_file = None
        largest_size = 0
        current_file = None
        current_size = 0

        for line in lines:
            line = line.lstrip()
            if line.startswith("Path = "):
                current_file = line.split(" = ", 1)[1]
            elif line.startswith("Size = "):
                try:
                    current_size = int(line.split(" = ")[1].strip())
                except ValueError:
                    current_size = 0
            elif line.startswith("Attributes = "):
                # Check if this is a file (not a folder)
                attrs = line.split(" = ")[1].strip()
                if current_file and not attrs.startswith("D"):  # D indicates directory
                    if current_size > largest_size:
                        largest_size = current_size
                        largest_file = current_file

        if not largest_file:
            return False

        log.debug(f"Extracting {largest_file} from {file_path}...")

        start_decompression_time = time.monotonic()

        with subprocess.Popen(
            [SEVEN_ZIP_PATH, "e", str(file_path), largest_file, "-so", "-y"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,  # trunk-ignore(bandit/B603): 7z path is hardcoded, args are validated
        ) as process:
            if process.stdout:
                while chunk := process.stdout.read(FILE_READ_CHUNK_SIZE):
                    elapsed_time = time.monotonic() - start_decompression_time

                    if elapsed_time > SEVEN_ZIP_TIMEOUT:
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


def _stream_7z_chunks(
    process: subprocess.Popen[bytes], deadline: float
) -> Iterator[bytes]:
    assert process.stdout is not None
    while chunk := process.stdout.read(FILE_READ_CHUNK_SIZE):
        if time.monotonic() > deadline:
            process.terminate()
            log.error("7z extraction timed out during multi-file archive read")
            return
        yield chunk


def read_7z_archive_files(
    file_path: Path,
    excluded_names: list[str],
    excluded_exts: list[str],
) -> Iterator[tuple[str, int, Iterator[bytes]]]:
    """Yield eligible files from a 7z archive in ASCII path order.

    Each yielded `(internal_name, file_size_bytes, chunks)` streams its
    member's bytes lazily; chunks must be fully consumed before advancing
    to the next entry, since the underlying subprocess is reaped at that point.
    """
    try:
        result = subprocess.run(
            [SEVEN_ZIP_PATH, "l", "-slt", "-ba", str(file_path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=SEVEN_ZIP_TIMEOUT,
            shell=False,  # trunk-ignore(bandit/B603)
        )
    except (
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
        FileNotFoundError,
    ) as e:
        log.error(f"Error listing 7z archive {file_path}: {e}")
        return

    entries: list[tuple[str, int]] = []
    current_file: str | None = None
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
                base_name = Path(current_file).name
                lower = base_name.lower()
                if not any(lower.endswith("." + ext) for ext in excluded_exts):
                    if not any(
                        base_name == exc or fnmatch.fnmatch(base_name, exc)
                        for exc in excluded_names
                    ):
                        entries.append((current_file, current_size))
            current_file = None
            current_size = 0

    entries.sort(key=lambda e: e[0])

    deadline = time.monotonic() + SEVEN_ZIP_TIMEOUT

    for name, size in entries:
        try:
            with subprocess.Popen(
                [SEVEN_ZIP_PATH, "e", str(file_path), name, "-so", "-y"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                shell=False,  # trunk-ignore(bandit/B603)
            ) as process:
                if process.stdout is None:
                    continue
                yield name, size, _stream_7z_chunks(process, deadline)
            if process.returncode != 0:
                log.error(
                    f"7z extraction of {name} failed with code {process.returncode}"
                )
                return []
        except (OSError, ValueError) as e:
            log.error(f"Error extracting {name} from {file_path}: {e}")
            continue


def read_rar_archive_files(
    file_path: Path,
    excluded_names: list[str],
    excluded_exts: list[str],
) -> Iterator[tuple[str, int, Iterator[bytes]]]:
    """Yield eligible files from a RAR archive, sorted by internal path (ASCII).

    Delegates to the 7zz binary, which natively supports RAR (v3-v5, read-only).
    """
    return read_7z_archive_files(file_path, excluded_names, excluded_exts)
