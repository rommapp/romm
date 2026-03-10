# trunk-ignore-all(bandit/B404)

import subprocess
import time
from collections.abc import Callable
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

    All files within the archive are processed in alphabetical order to produce a
    deterministic combined hash. This ensures multi-file archives (e.g. MAME ROM sets)
    yield a unique hash per game rather than matching on a single shared file, which
    could cause false positive identification across different games.

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

        # Collect all files (not directories), then sort alphabetically for
        # deterministic hashing across archives with different internal ordering.
        all_files: list[str] = []
        current_file = None
        is_directory = False

        for line in lines:
            line = line.lstrip()
            if line.startswith("Path = "):
                current_file = line.split(" = ", 1)[1]
                is_directory = False
            elif line.startswith("Attributes = "):
                attrs = line.split(" = ")[1].strip()
                is_directory = attrs.startswith("D")  # D indicates directory
                if current_file and not is_directory:
                    all_files.append(current_file)

        if not all_files:
            return False

        all_files.sort()

        for file_name in all_files:
            log.debug(f"Extracting {file_name} from {file_path}...")

            start_decompression_time = time.monotonic()

            with subprocess.Popen(
                [SEVEN_ZIP_PATH, "e", str(file_path), file_name, "-so", "-y"],
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
                log.error(
                    f"7z extraction failed with return code {process.returncode}"
                )
                return False

        return True

    except (
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
        FileNotFoundError,
    ) as e:
        log.error(f"Error processing 7z file: {e}")
        return False
