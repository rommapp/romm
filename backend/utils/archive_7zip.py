# trunk-ignore-all(bandit/B404)

import subprocess
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

SEVEN_ZIP_PATH = "/usr/bin/7z"


def process_file_7z(
    file_path: Path,
    fn_hash_update: Callable[[bytes | bytearray], None],
) -> None:
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
            timeout=60,
            shell=False,  # trunk-ignore(bandit/B603): 7z path is hardcoded, args are validated
        )

        lines = result.stdout.split("\n")
        first_file = None

        for line in lines:
            if line.strip().startswith("Path"):
                first_file = line.split(" = ")[1].strip()
                break

        if not first_file:
            for chunk in read_basic_file(file_path):
                fn_hash_update(chunk)
            return

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Extract only the first file
            subprocess.run(
                [
                    SEVEN_ZIP_PATH,
                    "e",
                    str(file_path),
                    first_file,
                    f"-o{temp_path}",
                    "-y",
                ],
                capture_output=True,
                check=True,
                timeout=60,
                shell=False,  # trunk-ignore(bandit/B603): 7z path is hardcoded, args are validated
            )

            extracted_file = temp_path / first_file
            if extracted_file.exists():
                with open(extracted_file, "rb") as f:
                    while chunk := f.read(8192):
                        fn_hash_update(chunk)
            else:
                for chunk in read_basic_file(file_path):
                    fn_hash_update(chunk)

    except (
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
        FileNotFoundError,
    ):
        for chunk in read_basic_file(file_path):
            fn_hash_update(chunk)


def read_basic_file(file_path: Path) -> Iterator[bytes]:
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            yield chunk
