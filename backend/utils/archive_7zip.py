# trunk-ignore-all(bandit/B404)

import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from config import ROMM_TMP_PATH, SEVEN_ZIP_TIMEOUT
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
            line = line.strip()
            if line.startswith("Path = "):
                current_file = line.split(" = ")[1].strip()
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

        with tempfile.TemporaryDirectory(dir=ROMM_TMP_PATH) as temp_dir:
            log.debug(f"Extracting {largest_file} from {file_path}...")

            temp_path = Path(temp_dir)
            subprocess.run(
                [
                    SEVEN_ZIP_PATH,
                    "e",
                    str(file_path),
                    largest_file,
                    f"-o{temp_path}",
                    "-y",
                ],
                capture_output=True,
                check=True,
                timeout=SEVEN_ZIP_TIMEOUT,
                shell=False,  # trunk-ignore(bandit/B603): 7z path is hardcoded, args are validated
            )

            # Get the first file in temp_path
            extracted_file = next(temp_path.iterdir(), None)
            if extracted_file and extracted_file.exists():
                with open(extracted_file, "rb") as f:
                    while chunk := f.read(FILE_READ_CHUNK_SIZE):
                        fn_hash_update(chunk)

                return True
            return False

    except (
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
        FileNotFoundError,
    ) as e:
        log.error(f"Error processing 7z file: {e}")
        return False
