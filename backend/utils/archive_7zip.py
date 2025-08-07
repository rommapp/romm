import subprocess
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path


def process_file(
    file_path: Path,
    fn_hash_update: Callable[[bytes | bytearray], None],
    fn_hash_read: Callable[[int | None], bytes],
) -> None:
    """Process a 7zip file using the system's 7zip binary and use the provided callables to update the calculated hashes.

    This function uses the system's 7zip binary to list the archive contents and extract the first file
    to calculate hashes, avoiding the memory-intensive py7zr library.

    Args:
        file_path: Path to the 7z file
        fn_hash_update: Callback to update hashes with data chunks
        fn_hash_read: Callback that returns current hash digest (unused in this implementation)
    """

    try:
        result = subprocess.run(
            ["7z", "l", str(file_path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )

        lines = result.stdout.split("\n")
        first_file = None

        # Look for the line that contains the actual file entry
        for line in lines:
            line = line.strip()
            if "....A" in line:
                parts = line.split()
                if len(parts) >= 4:
                    first_file = parts[-1]  # Last part is the filename
                    break

        if not first_file:
            # If no files found, fall back to reading the archive as a basic file
            for chunk in read_basic_file(file_path):
                fn_hash_update(chunk)
            return

        # Extract the first file to a temporary location
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Extract only the first file
            subprocess.run(
                ["7z", "e", str(file_path), first_file, f"-o{temp_path}", "-y"],
                capture_output=True,
                check=True,
                timeout=60,  # 60 second timeout for extraction
            )

            # Read the extracted file and update hashes
            extracted_file = temp_path / first_file
            if extracted_file.exists():
                with open(extracted_file, "rb") as f:
                    while chunk := f.read(8192):  # 8KB chunks
                        fn_hash_update(chunk)
            else:
                # Fall back to reading the archive as a basic file
                for chunk in read_basic_file(file_path):
                    fn_hash_update(chunk)

    except (
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
        FileNotFoundError,
    ):
        # If 7zip is not available or fails, fall back to reading the archive as a basic file
        for chunk in read_basic_file(file_path):
            fn_hash_update(chunk)


def read_basic_file(file_path: Path) -> Iterator[bytes]:
    """Read a file in chunks and yield the chunks."""
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):  # 8KB chunks
            yield chunk
