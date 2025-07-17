import fnmatch
import os
import re
import shutil
import threading
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from typing import Optional

from config.config_manager import config_manager as cm
from fastapi import UploadFile
from models.base import FILE_NAME_MAX_LENGTH
from utils.filesystem import iter_directories, iter_files

TAG_REGEX = re.compile(r"\(([^)]+)\)|\[([^]]+)\]")
EXTENSION_REGEX = re.compile(r"\.(([a-z]+\.)*\w+)$")

LANGUAGES = (
    ("Ar", "Arabic"),
    ("Da", "Danish"),
    ("De", "German"),
    ("En", "English"),
    ("Es", "Spanish"),
    ("Fi", "Finnish"),
    ("Fr", "French"),
    ("It", "Italian"),
    ("Ja", "Japanese"),
    ("Ko", "Korean"),
    ("Nl", "Dutch"),
    ("No", "Norwegian"),
    ("Pl", "Polish"),
    ("Pt", "Portuguese"),
    ("Ru", "Russian"),
    ("Sv", "Swedish"),
    ("Zh", "Chinese"),
    ("nolang", "No Language"),
)

REGIONS = (
    ("A", "Australia"),
    ("AS", "Asia"),
    ("B", "Brazil"),
    ("C", "Canada"),
    ("CH", "China"),
    ("E", "Europe"),
    ("F", "France"),
    ("FN", "Finland"),
    ("G", "Germany"),
    ("GR", "Greece"),
    ("H", "Holland"),
    ("HK", "Hong Kong"),
    ("I", "Italy"),
    ("J", "Japan"),
    ("K", "Korea"),
    ("NL", "Netherlands"),
    ("NO", "Norway"),
    ("PD", "Public Domain"),
    ("R", "Russia"),
    ("S", "Spain"),
    ("SW", "Sweden"),
    ("T", "Taiwan"),
    ("U", "USA"),
    ("UK", "England"),
    ("UNK", "Unknown"),
    ("UNL", "Unlicensed"),
    ("W", "World"),
)

REGIONS_BY_SHORTCODE = {region[0].lower(): region[1] for region in REGIONS}
REGIONS_NAME_KEYS = frozenset(region[1].lower() for region in REGIONS)

LANGUAGES_BY_SHORTCODE = {lang[0].lower(): lang[1] for lang in LANGUAGES}
LANGUAGES_NAME_KEYS = frozenset(lang[1].lower() for lang in LANGUAGES)


class CoverSize(Enum):
    SMALL = "small"
    BIG = "big"


class Asset(Enum):
    SAVES = "saves"
    STATES = "states"
    SCREENSHOTS = "screenshots"


class FSHandler:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path).resolve()
        self._locks: dict[str, threading.Lock] = {}
        self._lock_mutex = threading.Lock()

    def _get_file_lock(self, file_path: str) -> threading.Lock:
        """Get or create a lock for a specific file path."""
        with self._lock_mutex:
            if file_path not in self._locks:
                self._locks[file_path] = threading.Lock()
            return self._locks[file_path]

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal and other attacks."""
        if not filename:
            raise ValueError("Empty filename")

        # Remove path components and get basename only
        filename = os.path.basename(filename)

        # Limit filename length
        if len(filename) > FILE_NAME_MAX_LENGTH:
            raise ValueError(
                f"Filename exceeds maximum length of {FILE_NAME_MAX_LENGTH} characters"
            )

        # Ensure we have a valid filename
        if not filename or filename == "." or filename == "..":
            raise ValueError("Invalid filename")

        return filename

    def _validate_path(self, path: str) -> Path:
        """Validate and normalize path to prevent directory traversal."""
        if not path:
            raise ValueError("Empty path")

        path_path = Path(path)

        # Check for explicit parent directory references
        if ".." in path_path.parts:
            raise ValueError("Path contains invalid parent directory references")

        # Check for absolute paths
        if path_path.is_absolute():
            raise ValueError("Path must be relative, not absolute")

        # Normalize path
        base_path_obj = Path(self.base_path).resolve()
        full_path = (base_path_obj / path_path).resolve()

        # Ensure path is within base directory
        full_path.relative_to(base_path_obj)

        return full_path

    @contextmanager
    def _atomic_write(self, target_path: Path):
        """Context manager for atomic file writing."""
        temp_path = None
        try:
            # Create temporary file in same directory
            temp_path = target_path.parent / f".tmp_{target_path.name}_{os.getpid()}"
            yield temp_path

            # Atomic move to final location
            shutil.move(str(temp_path), str(target_path))

        except Exception:
            # Clean up temporary file on error
            if temp_path and temp_path.exists():
                temp_path.unlink()
            raise

    def get_file_name_with_no_extension(self, file_name: str) -> str:
        return EXTENSION_REGEX.sub("", file_name).strip()

    def get_file_name_with_no_tags(self, file_name: str) -> str:
        file_name_no_extension = self.get_file_name_with_no_extension(file_name)
        return TAG_REGEX.split(file_name_no_extension)[0].strip()

    def parse_file_extension(self, file_name: str) -> str:
        match = EXTENSION_REGEX.search(file_name)
        return match.group(1) if match else ""

    def exclude_single_files(self, files: list[str]) -> list[str]:
        excluded_extensions = cm.get_config().EXCLUDED_SINGLE_EXT
        excluded_names = cm.get_config().EXCLUDED_SINGLE_FILES
        excluded_files: list = []

        for file_name in files:
            # Split the file name to get the extension.
            ext = self.parse_file_extension(file_name)

            # Exclude the file if it has no extension or the extension is in the excluded list.
            if not ext or ext in excluded_extensions:
                excluded_files.append(file_name)

            # Additionally, check if the file name mathes a pattern in the excluded list.
            for name in excluded_names:
                if file_name == name or fnmatch.fnmatch(file_name, name):
                    excluded_files.append(file_name)

        # Return files that are not in the filtered list.
        return [f for f in files if f not in excluded_files]

    def make_directory(self, path: str) -> None:
        """
        Create a directory at the specified path.
        Args:
            path: Relative path within base directory

        Raises:
            ValueError: If path is invalid or already exists as a file
        """
        target_directory = self._validate_path(path)

        # Thread-safe directory creation
        with self._get_file_lock(str(target_directory)):
            if not target_directory.exists():
                target_directory.mkdir(parents=True, exist_ok=True)
            elif not target_directory.is_dir():
                raise ValueError(
                    f"Path already exists and is not a directory: {target_directory}"
                )

    def list_directories(self, path: str) -> list[str]:
        """
        List all directories in a given path.

        Args:
            path: Relative path within base directory

        Returns:
            List of directory names in the specified path

        Raises:
            ValueError: If path is invalid or not a directory
        """
        target_directory = self._validate_path(path)

        # Thread-safe directory creation
        with self._get_file_lock(str(target_directory)):
            if not target_directory.exists() or not target_directory.is_dir():
                raise ValueError(
                    f"Path does not exist or is not a directory: {target_directory}"
                )

            return [
                d for _, d in iter_directories(str(target_directory), recursive=False)
            ]

    def remove_directory(self, path: str) -> None:
        """
        Remove a directory and all its contents.

        Args:
            path: Relative path within base directory

        Raises:
            ValueError: If path is invalid or not a directory
        """
        target_directory = self._validate_path(path)

        # Thread-safe directory removal
        with self._get_file_lock(str(target_directory)):
            if not target_directory.exists() or not target_directory.is_dir():
                raise ValueError(
                    f"Path does not exist or is not a directory: {target_directory}"
                )

            shutil.rmtree(target_directory, ignore_errors=False)

    def write_file(
        self, file: UploadFile, path: str, filename: Optional[str] = None
    ) -> None:
        """
        Securely write file to filesystem.

        Args:
            file: File object to write (UploadFile)
            path: Relative path within base directory
            filename: Optional filename override
            overwrite: Allow overwriting existing files

        Returns:
            Dictionary with operation result and file info
        """

        original_filename = filename or file.filename

        if not original_filename:
            raise ValueError("Filename cannot be empty")

        # Validate and sanitize inputs
        sanitized_filename = self._sanitize_filename(original_filename)
        target_directory = self._validate_path(path)

        final_file_path = target_directory / sanitized_filename

        # Thread-safe file operations
        with self._get_file_lock(str(final_file_path)):
            # Ensure target directory exists
            target_directory.mkdir(parents=True, exist_ok=True)

            # Write file atomically
            with self._atomic_write(final_file_path) as temp_path:
                with open(temp_path, "wb") as temp_file:
                    shutil.copyfileobj(file.file, temp_file)

    def read_file(self, file_path: str) -> bytes:
        """
        Read file from filesystem.

        Args:
            file_path: Relative path to the file

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file does not exist
        """
        if not file_path:
            raise ValueError("File path cannot be empty")

        # Validate and normalize path
        full_path = self._validate_path(file_path)

        # Thread-safe file read
        with self._get_file_lock(str(full_path)):
            if not full_path.exists() or not full_path.is_file():
                raise FileNotFoundError(f"File not found: {full_path}")

            with open(full_path, "rb") as f:
                return f.read()

    def stream_file(self, file_path: str):
        """
        Stream file from filesystem.

        Args:
            file_path: Relative path to the file

        Returns:
            File content as a stream

        Raises:
            FileNotFoundError: If file does not exist
        """
        if not file_path:
            raise ValueError("File path cannot be empty")

        # Validate and normalize path
        full_path = self._validate_path(file_path)

        # Thread-safe file stream
        with self._get_file_lock(str(full_path)):
            if not full_path.exists() or not full_path.is_file():
                raise FileNotFoundError(f"File not found: {full_path}")

            return open(full_path, "rb")

    def move_file(self, source_path: str, dest_path: str) -> None:
        """
        Move a file from source to destination.

        Args:
            source_path: Relative path to the source file
            dest_path: Relative path to the destination file

        Raises:
            FileNotFoundError: If source file does not exist
            ValueError: If destination path is invalid
        """
        if not source_path or not dest_path:
            raise ValueError("Source and destination paths cannot be empty")

        # Validate and normalize paths
        source_full_path = self._validate_path(source_path)
        dest_full_path = self._validate_path(dest_path)

        # Use locks for both source and destination
        source_lock = self._get_file_lock(str(source_full_path))
        dest_lock = self._get_file_lock(str(dest_full_path))

        # Thread-safe file move
        with source_lock, dest_lock:
            if not source_full_path.exists() or not source_full_path.is_file():
                raise FileNotFoundError(f"Source file not found: {source_full_path}")

            # Create destination directory if needed
            dest_full_path.parent.mkdir(parents=True, exist_ok=True)

            shutil.move(str(source_full_path), str(dest_full_path))

    def remove_file(self, file_path: str) -> None:
        """
        Remove a file from the filesystem.

        Args:
            file_path: Relative path to the file to remove

        Raises:
            FileNotFoundError: If file does not exist
        """
        if not file_path:
            raise ValueError("File path cannot be empty")

        # Validate and normalize path
        full_path = self._validate_path(file_path)

        # Thread-safe file removal
        with self._get_file_lock(str(full_path)):
            if not full_path.exists():
                raise FileNotFoundError(f"File not found: {full_path}")

            full_path.unlink()

    def list_files(self, path: str) -> list[str]:
        """
        List all files in a directory.

        Args:
            directory: Relative path to the directory

        Returns:
            List of file names in the directory

        Raises:
            FileNotFoundError: If directory does not exist
        """
        if not path:
            raise ValueError("Directory cannot be empty")

        # Validate and normalize path
        full_path = self._validate_path(path)

        # Thread-safe directory listing
        with self._get_file_lock(str(full_path)):
            if not full_path.exists() or not full_path.is_dir():
                raise FileNotFoundError(f"Directory not found: {full_path}")

            return [f for _, f in iter_files(str(full_path), recursive=False)]

    def file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists.

        Args:
            file_path: Relative path to the file

        Returns:
            True if file exists, False otherwise
        """
        if not file_path:
            raise ValueError("File path cannot be empty")

        # Validate and normalize path
        full_path = self._validate_path(file_path)

        # Thread-safe existence check
        with self._get_file_lock(str(full_path)):
            return full_path.exists() and full_path.is_file()

    def get_file_size(self, file_path: str) -> int:
        """
        Get the size of a file.

        Args:
            file_path: Relative path to the file

        Returns:
            Size of the file in bytes

        Raises:
            FileNotFoundError: If file does not exist
        """
        if not file_path:
            raise ValueError("File path cannot be empty")

        # Validate and normalize path
        full_path = self._validate_path(file_path)

        # Thread-safe file size retrieval
        with self._get_file_lock(str(full_path)):
            if not full_path.exists() or not full_path.is_file():
                raise FileNotFoundError(f"File not found: {full_path}")

            return full_path.stat().st_size
