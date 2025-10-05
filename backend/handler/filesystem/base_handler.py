import asyncio
import fnmatch
import os
import re
import shutil
from contextlib import asynccontextmanager
from enum import Enum
from io import BytesIO
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import BinaryIO

from anyio import open_file
from starlette.datastructures import UploadFile

from config.config_manager import config_manager as cm
from models.base import FILE_NAME_MAX_LENGTH
from utils.filesystem import iter_directories, iter_files

TAG_REGEX = re.compile(r"\(([^)]+)\)|\[([^]]+)\]")
EXTENSION_REGEX = re.compile(r"\.(([a-z]+\.)*\w+)$")

LANGUAGES = (
    ("Af", "Afrikaans"),
    ("Ar", "Arabic"),
    ("Be", "Belarusian"),
    ("Bg", "Bulgarian"),
    ("Ca", "Catalan"),
    ("Cs", "Czech"),
    ("Da", "Danish"),
    ("De", "German"),
    ("El", "Greek"),
    ("En", "English"),
    ("Es", "Spanish"),
    ("Et", "Estonian"),
    ("Eu", "Basque"),
    ("Fi", "Finnish"),
    ("Fr", "French"),
    ("Gd", "Gaelic"),
    ("He", "Hebrew"),
    ("Hi", "Hindi"),
    ("Hr", "Croatian"),
    ("Hu", "Hungarian"),
    ("Hy", "Armenian"),
    ("Id", "Indonesian"),
    ("Is", "Icelandic"),
    ("It", "Italian"),
    ("Ja", "Japanese"),
    ("Ko", "Korean"),
    ("La", "Latin"),
    ("Lt", "Lithuanian"),
    ("Lv", "Latvian"),
    ("Mk", "Macedonian"),
    ("Nl", "Dutch"),
    ("No", "Norwegian"),
    ("Pa", "Punjabi"),
    ("Pl", "Polish"),
    ("Pt", "Portuguese"),
    ("Ro", "Romanian"),
    ("Ru", "Russian"),
    ("Sk", "Slovak"),
    ("Sl", "Slovenian"),
    ("Sq", "Albanian"),
    ("Sr", "Serbian"),
    ("Sv", "Swedish"),
    ("Ta", "Tamil"),
    ("Th", "Thai"),
    ("Tr", "Turkish"),
    ("Uk", "Ukrainian"),
    ("Vi", "Vietnamese"),
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
        self._locks: dict[str, asyncio.Lock] = {}
        self._lock_mutex = asyncio.Lock()

        # Create base directory synchronously during initialization
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def _get_file_lock(self, file_path: str) -> asyncio.Lock:
        """Get or create a lock for a specific file path."""
        async with self._lock_mutex:
            if file_path not in self._locks:
                self._locks[file_path] = asyncio.Lock()
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

    def validate_path(self, path: str) -> Path:
        """Validate and normalize path to prevent directory traversal."""
        path_path = Path(path)

        # Check for explicit parent directory references
        if ".." in path_path.parts:
            raise ValueError("Path contains invalid parent directory references")

        # Check for absolute paths
        if path_path.is_absolute():
            raise ValueError("Path must be relative, not absolute")

        # Normalize path without resolving the full path yet
        base_path_obj = Path(self.base_path).resolve()
        full_path = base_path_obj / path_path

        try:
            if full_path.is_symlink():
                # For symlinks, ensure the symlink itself is within base directory
                full_path.relative_to(base_path_obj)
            else:
                # For regular files/dirs, ensure resolved path is within base directory
                full_path.resolve().relative_to(base_path_obj)
        except ValueError as exc:
            raise ValueError(
                f"Path {path} is outside the base directory {self.base_path}"
            ) from exc

        return full_path

    @asynccontextmanager
    async def _atomic_write(self, target_path: Path):
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
        excluded_files: list[str] = []

        for file_name in files:
            # Split the file name to get the extension.
            ext = self.parse_file_extension(file_name)

            # Exclude the file if it has no extension or the extension is in the excluded list.
            if ext and ext.lower() in excluded_extensions:
                excluded_files.append(file_name)

            # Additionally, check if the file name mathes a pattern in the excluded list.
            for name in excluded_names:
                if file_name == name or fnmatch.fnmatch(file_name, name):
                    excluded_files.append(file_name)

        # Return files that are not in the filtered list.
        return [f for f in files if f not in excluded_files]

    async def make_directory(self, path: str) -> None:
        """
        Create a directory at the specified path.
        Args:
            path: Relative path within base directory

        Raises:
            ValueError: If path is invalid
            FileNotFoundError: If path is not a directory
        """
        target_directory = self.validate_path(path)

        # Async thread-safe directory creation
        lock = await self._get_file_lock(str(target_directory))
        async with lock:
            if not target_directory.exists():
                target_directory.mkdir(parents=True, exist_ok=True)
            elif not target_directory.is_dir():
                raise FileNotFoundError(
                    f"Path already exists and is not a directory: {str(target_directory)}"
                )

    async def list_directories(self, path: str) -> list[str]:
        """
        List all directories in a given path.

        Args:
            path: Relative path within base directory

        Returns:
            List of directory names in the specified path

        Raises:
            FileNotFoundError: If path is invalid or not a directory
        """
        target_directory = self.validate_path(path)

        # Async thread-safe directory listing
        lock = await self._get_file_lock(str(target_directory))
        async with lock:
            if not target_directory.exists() or not target_directory.is_dir():
                raise FileNotFoundError(
                    f"Path does not exist or is not a directory: {str(target_directory)}"
                )

            return [
                d for _, d in iter_directories(str(target_directory), recursive=False)
            ]

    async def remove_directory(self, path: str) -> None:
        """
        Remove a directory and all its contents.

        Args:
            path: Relative path within base directory

        Raises:
            FileNotFoundError: If path is invalid or not a directory
        """
        target_directory = self.validate_path(path)

        # Async thread-safe directory removal
        lock = await self._get_file_lock(str(target_directory))
        async with lock:
            if not target_directory.exists() or not target_directory.is_dir():
                raise FileNotFoundError(
                    f"Path does not exist or is not a directory: {str(target_directory)}"
                )

            shutil.rmtree(target_directory, ignore_errors=False)

    async def write_file(
        self,
        file: UploadFile | BinaryIO | BytesIO | bytes | SpooledTemporaryFile,
        path: str,
        filename: str | None = None,
    ) -> None:
        """
        Securely write file to filesystem.

        Args:
            file: File-like object to write
            path: Relative path within base directory
            filename: Optional filename override

        Returns:
            Dictionary with operation result and file info
        """

        original_filename = filename or getattr(file, "filename", None)
        if not original_filename:
            raise ValueError("Filename cannot be empty")

        # Validate and sanitize inputs
        sanitized_filename = self._sanitize_filename(original_filename)
        target_directory = self.validate_path(path)

        final_file_path = target_directory / sanitized_filename

        # Async thread-safe file operations
        lock = await self._get_file_lock(str(final_file_path))
        async with lock:
            # Ensure target directory exists
            target_directory.mkdir(parents=True, exist_ok=True)

            # Write file atomically
            async with self._atomic_write(final_file_path) as temp_path:
                async with await open_file(temp_path, "wb") as temp_file:
                    if isinstance(file, UploadFile):
                        while chunk := file.file.read(8192):
                            await temp_file.write(chunk)
                    elif isinstance(file, BinaryIO) or isinstance(
                        file, SpooledTemporaryFile
                    ):
                        file.seek(0)
                        while chunk := file.read(8192):
                            await temp_file.write(chunk)
                    elif isinstance(file, BytesIO):
                        await temp_file.write(file.getvalue())
                    elif isinstance(file, bytes):
                        await temp_file.write(file)
                    else:
                        raise ValueError("Unsupported file type for writing")

    async def write_file_streamed(self, path: str, filename: str):
        """
        Write file to filesystem using a streamed approach.

        Args:
            path: Relative path within base directory
            filename: Name of the file to write

        Returns:
            File object for writing

        Raises:
            ValueError: If path or filename is invalid
        """
        if not path or not filename:
            raise ValueError("Path and filename cannot be empty")

        # Validate and sanitize inputs
        sanitized_filename = self._sanitize_filename(filename)
        target_directory = self.validate_path(path)

        final_file_path = target_directory / sanitized_filename

        # Async thread-safe file operations
        lock = await self._get_file_lock(str(final_file_path))
        async with lock:
            # Ensure target directory exists
            target_directory.mkdir(parents=True, exist_ok=True)

            # Open file for writing
            return await open_file(final_file_path, "wb")

    async def read_file(self, file_path: str) -> bytes:
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
        full_path = self.validate_path(file_path)

        # Async thread-safe file read
        lock = await self._get_file_lock(str(full_path))
        async with lock:
            if not full_path.exists() or not full_path.is_file():
                raise FileNotFoundError(f"File not found: {full_path}")

            async with await open_file(full_path, "rb") as f:
                return await f.read()

    async def stream_file(self, file_path: str):
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
        full_path = self.validate_path(file_path)

        # Async thread-safe file stream
        lock = await self._get_file_lock(str(full_path))
        async with lock:
            if not full_path.exists() or not full_path.is_file():
                raise FileNotFoundError(f"File not found: {full_path}")

            return await open_file(full_path, "rb")

    async def move_file_or_folder(self, source_path: str, dest_path: str) -> None:
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
        source_full_path = self.validate_path(source_path)
        dest_full_path = self.validate_path(dest_path)

        # Use locks for both source and destination
        source_lock = await self._get_file_lock(str(source_full_path))
        dest_lock = await self._get_file_lock(str(dest_full_path))

        # Async thread-safe file move
        async with source_lock, dest_lock:
            if not source_full_path.exists():
                raise FileNotFoundError(
                    f"Source file or folder not found: {source_full_path}"
                )

            # Create destination directory if needed
            dest_full_path.parent.mkdir(parents=True, exist_ok=True)

            shutil.move(str(source_full_path), str(dest_full_path))

    async def remove_file(self, file_path: str) -> None:
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
        full_path = self.validate_path(file_path)

        # Async thread-safe file removal
        lock = await self._get_file_lock(str(full_path))
        async with lock:
            if not full_path.exists():
                raise FileNotFoundError(f"File not found: {full_path}")

            full_path.unlink()

    async def list_files(self, path: str) -> list[str]:
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
        full_path = self.validate_path(path)

        # Async thread-safe directory listing
        lock = await self._get_file_lock(str(full_path))
        async with lock:
            if not full_path.exists() or not full_path.is_dir():
                raise FileNotFoundError(f"Directory not found: {full_path}")

            return [f for _, f in iter_files(str(full_path), recursive=False)]

    async def file_exists(self, file_path: str) -> bool:
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
        full_path = self.validate_path(file_path)

        # Async thread-safe existence check
        lock = await self._get_file_lock(str(full_path))
        async with lock:
            return full_path.exists() and full_path.is_file()

    async def get_file_size(self, file_path: str) -> int:
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
        full_path = self.validate_path(file_path)

        # Async thread-safe file size retrieval
        lock = await self._get_file_lock(str(full_path))
        async with lock:
            if not full_path.exists() or not full_path.is_file():
                raise FileNotFoundError(f"File not found: {full_path}")

            return full_path.stat().st_size
