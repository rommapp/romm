import asyncio
import shutil
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi import UploadFile

from handler.filesystem.base_handler import FSHandler
from models.base import FILE_NAME_MAX_LENGTH


class TestFSHandler:
    """Test suite for FSHandler class"""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def handler(self, temp_dir):
        """Create FSHandler instance for testing"""
        return FSHandler(temp_dir)

    @pytest.fixture
    def sample_file_content(self):
        """Sample file content for testing"""
        return b"This is test content for file operations"

    @pytest.fixture
    def mock_upload_file(self, sample_file_content):
        """Mock UploadFile for testing"""
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test_file.txt"
        mock_file.file = BytesIO(sample_file_content)
        return mock_file

    def test_init_creates_base_directory(self, temp_dir):
        """Test that FSHandler creates base directory on initialization"""
        # Remove the directory to test creation
        shutil.rmtree(temp_dir)

        handler = FSHandler(temp_dir)

        assert handler.base_path.exists()
        assert handler.base_path.is_dir()

    def test_init_resolves_path(self, temp_dir):
        """Test that FSHandler resolves the base path"""
        handler = FSHandler(temp_dir)

        assert handler.base_path == Path(temp_dir).resolve()

    def test_sanitize_filename_valid(self, handler: FSHandler):
        """Test filename sanitization with valid filenames"""
        assert handler._sanitize_filename("test.txt") == "test.txt"
        assert handler._sanitize_filename("file-name_123.zip") == "file-name_123.zip"
        assert handler._sanitize_filename("file.name.ext") == "file.name.ext"

    def test_sanitize_filename_path_traversal(self, handler: FSHandler):
        """Test filename sanitization prevents path traversal"""
        assert handler._sanitize_filename("../test.txt") == "test.txt"
        assert handler._sanitize_filename("../../test.txt") == "test.txt"
        assert handler._sanitize_filename("/etc/passwd") == "passwd"
        assert handler._sanitize_filename("dir/../test.txt") == "test.txt"

    def test_sanitize_filename_invalid(self, handler: FSHandler):
        """Test filename sanitization with invalid filenames"""
        with pytest.raises(ValueError, match="Empty filename"):
            handler._sanitize_filename("")

        with pytest.raises(ValueError, match="Invalid filename"):
            handler._sanitize_filename(".")

        with pytest.raises(ValueError, match="Invalid filename"):
            handler._sanitize_filename("..")

    def test_sanitize_filename_too_long(self, handler: FSHandler):
        """Test filename sanitization with too long filenames"""
        long_name = "a" * (FILE_NAME_MAX_LENGTH + 1)
        with pytest.raises(ValueError, match="Filename exceeds maximum length"):
            handler._sanitize_filename(long_name)

    def test_validate_path_valid(self, handler: FSHandler):
        """Test path validation with valid paths"""
        valid_paths = [
            "test.txt",
            "dir/test.txt",
            "dir/subdir/test.txt",
            "test-file_123.txt",
        ]

        for path in valid_paths:
            result = handler.validate_path(path)
            assert result.is_relative_to(handler.base_path)

    def test_validate_path_traversal_attack(self, handler: FSHandler):
        """Test path validation prevents directory traversal attacks"""
        malicious_paths = [
            "../test.txt",
            "../../etc/passwd",
            "dir/../../../etc/passwd",
            "dir/../../test.txt",
        ]

        for path in malicious_paths:
            with pytest.raises(
                ValueError, match="Path contains invalid parent directory references"
            ):
                handler.validate_path(path)

    def test_validate_path_absolute(self, handler: FSHandler):
        """Test path validation rejects absolute paths"""
        absolute_paths = ["/etc/passwd", "/tmp/test.txt", "/home/user/file.txt"]

        for path in absolute_paths:
            with pytest.raises(ValueError, match="Path must be relative, not absolute"):
                handler.validate_path(path)

    def test_get_file_name_with_no_extension(self, handler: FSHandler):
        """Test file name extraction without extension"""
        assert handler.get_file_name_with_no_extension("test.txt") == "test"
        assert handler.get_file_name_with_no_extension("file.tar.gz") == "file"
        assert handler.get_file_name_with_no_extension("file.with.dots.txt") == "file"
        assert handler.get_file_name_with_no_extension("no_extension") == "no_extension"

    def test_get_file_name_with_no_tags(self, handler: FSHandler):
        """Test file name extraction without tags"""
        assert handler.get_file_name_with_no_tags("game (USA).rom") == "game"
        assert handler.get_file_name_with_no_tags("game [Beta].rom") == "game"
        assert handler.get_file_name_with_no_tags("game (USA) [Beta].rom") == "game"
        assert handler.get_file_name_with_no_tags("plain_name.rom") == "plain_name"

    def test_parse_file_extension(self, handler: FSHandler):
        """Test file extension parsing"""
        assert handler.parse_file_extension("test.txt") == "txt"
        assert handler.parse_file_extension("file.tar.gz") == "tar.gz"
        assert handler.parse_file_extension("no_extension") == ""
        assert handler.parse_file_extension("file.with.dots.txt") == "with.dots.txt"

    def test_exclude_single_files(self, handler: FSHandler):
        """Test file exclusion functionality"""
        files = ["test.txt", "game.rom", "excluded.tmp", "data.json"]

        # Mock configuration
        with patch("handler.filesystem.base_handler.cm.get_config") as mock_config:
            mock_config.return_value.EXCLUDED_SINGLE_EXT = ["tmp"]
            mock_config.return_value.EXCLUDED_SINGLE_FILES = ["test.txt"]

            result = handler.exclude_single_files(files)

            assert "excluded.tmp" not in result
            assert "test.txt" not in result
            assert "game.rom" in result
            assert "data.json" in result

    async def test_make_directory(self, handler: FSHandler):
        """Test directory creation"""
        await handler.make_directory("test_dir")

        full_path = handler.base_path / "test_dir"
        assert full_path.exists()
        assert full_path.is_dir()

    async def test_make_directory_nested(self, handler: FSHandler):
        """Test nested directory creation"""
        await handler.make_directory("parent/child/grandchild")

        full_path = handler.base_path / "parent" / "child" / "grandchild"
        assert full_path.exists()
        assert full_path.is_dir()

    async def test_make_directory_exists(self, handler: FSHandler):
        """Test directory creation when directory already exists"""
        await handler.make_directory("test_dir")
        await handler.make_directory("test_dir")  # Should not raise error

        full_path = handler.base_path / "test_dir"
        assert full_path.exists()
        assert full_path.is_dir()

    async def test_make_directory_file_exists(self, handler: FSHandler):
        """Test directory creation when file with same name exists"""
        # Create a file first
        (handler.base_path / "test_file").touch()

        with pytest.raises(
            FileNotFoundError, match="Path already exists and is not a directory"
        ):
            await handler.make_directory("test_file")

    async def test_list_directories(self, handler: FSHandler):
        """Test directory listing"""
        # Create test directories
        await handler.make_directory("dir1")
        await handler.make_directory("dir2")
        await handler.make_directory("parent/child")

        # Create a file (should not be listed)
        (handler.base_path / "file.txt").touch()

        dirs = await handler.list_directories(".")
        assert "dir1" in dirs
        assert "dir2" in dirs
        assert "parent" in dirs
        assert "file.txt" not in dirs

    async def test_list_directories_nonexistent(self, handler: FSHandler):
        """Test directory listing with nonexistent directory"""
        with pytest.raises(
            FileNotFoundError, match="Path does not exist or is not a directory"
        ):
            await handler.list_directories("nonexistent")

    async def test_remove_directory(self, handler: FSHandler):
        """Test directory removal"""
        # Create directory with content
        await handler.make_directory("test_dir/subdir")
        (handler.base_path / "test_dir" / "file.txt").touch()

        await handler.remove_directory("test_dir")

        assert not (handler.base_path / "test_dir").exists()

    async def test_remove_directory_nonexistent(self, handler: FSHandler):
        """Test directory removal with nonexistent directory"""
        with pytest.raises(
            FileNotFoundError, match="Path does not exist or is not a directory"
        ):
            await handler.remove_directory("nonexistent")

    async def test_write_file_upload_file(self, handler: FSHandler, mock_upload_file):
        """Test file writing with UploadFile"""
        await handler.write_file(mock_upload_file, ".", "test_file.txt")

        file_path = handler.base_path / "test_file.txt"
        assert file_path.exists()
        assert file_path.read_bytes() == b"This is test content for file operations"

    async def test_write_file_bytes(self, handler: FSHandler, sample_file_content):
        """Test file writing with bytes"""
        await handler.write_file(sample_file_content, ".", "test_file.txt")

        file_path = handler.base_path / "test_file.txt"
        assert file_path.exists()
        assert file_path.read_bytes() == sample_file_content

    async def test_write_file_binary_io(self, handler: FSHandler, sample_file_content):
        """Test file writing with BinaryIO"""
        bio = BytesIO(sample_file_content)
        await handler.write_file(bio, ".", "test_file.txt")

        file_path = handler.base_path / "test_file.txt"
        assert file_path.exists()
        assert file_path.read_bytes() == sample_file_content

    async def test_write_file_nested_path(
        self, handler: FSHandler, sample_file_content
    ):
        """Test file writing in nested path"""
        await handler.write_file(sample_file_content, "parent/child", "test_file.txt")

        file_path = handler.base_path / "parent" / "child" / "test_file.txt"
        assert file_path.exists()
        assert file_path.read_bytes() == sample_file_content

    async def test_write_file_no_filename(
        self, handler: FSHandler, sample_file_content
    ):
        """Test file writing without filename"""
        with pytest.raises(ValueError, match="Filename cannot be empty"):
            await handler.write_file(sample_file_content, ".", None)

    async def test_write_file_streamed(self, handler: FSHandler, sample_file_content):
        """Test streamed file writing"""
        async with await handler.write_file_streamed(".", "test_file.txt") as f:
            await f.write(sample_file_content)

        file_path = handler.base_path / "test_file.txt"
        assert file_path.exists()
        assert file_path.read_bytes() == sample_file_content

    async def test_read_file(self, handler: FSHandler, sample_file_content):
        """Test file reading"""
        # Write file first
        await handler.write_file(sample_file_content, ".", "test_file.txt")

        # Read file
        content = await handler.read_file("test_file.txt")
        assert content == sample_file_content

    async def test_read_file_nonexistent(self, handler: FSHandler):
        """Test reading nonexistent file"""
        with pytest.raises(FileNotFoundError, match="File not found"):
            await handler.read_file("nonexistent.txt")

    async def test_stream_file(self, handler: FSHandler, sample_file_content):
        """Test file streaming"""
        # Write file first
        await handler.write_file(sample_file_content, ".", "test_file.txt")

        # Stream file
        async with await handler.stream_file("test_file.txt") as f:
            content = await f.read()

        assert content == sample_file_content

    async def test_stream_file_nonexistent(self, handler: FSHandler):
        """Test streaming nonexistent file"""
        with pytest.raises(FileNotFoundError, match="File not found"):
            await handler.stream_file("nonexistent.txt")

    async def test_move_file(self, handler: FSHandler, sample_file_content):
        """Test file moving"""
        # Write source file
        await handler.write_file(sample_file_content, ".", "source.txt")

        # Move file
        await handler.move_file_or_folder("source.txt", "destination.txt")

        assert not (handler.base_path / "source.txt").exists()
        assert (handler.base_path / "destination.txt").exists()
        assert (
            handler.base_path / "destination.txt"
        ).read_bytes() == sample_file_content

    async def test_move_file_to_nested_path(
        self, handler: FSHandler, sample_file_content
    ):
        """Test moving file to nested path"""
        # Write source file
        await handler.write_file(sample_file_content, ".", "source.txt")

        # Move file to nested path
        await handler.move_file_or_folder("source.txt", "parent/child/destination.txt")

        assert not (handler.base_path / "source.txt").exists()
        assert (handler.base_path / "parent" / "child" / "destination.txt").exists()

    async def test_move_file_nonexistent(self, handler: FSHandler):
        """Test moving nonexistent file"""
        with pytest.raises(FileNotFoundError, match="Source file or folder not found"):
            await handler.move_file_or_folder("nonexistent.txt", "destination.txt")

    async def test_remove_file(self, handler: FSHandler, sample_file_content):
        """Test file removal"""
        # Write file first
        await handler.write_file(sample_file_content, ".", "test_file.txt")

        # Remove file
        await handler.remove_file("test_file.txt")

        assert not (handler.base_path / "test_file.txt").exists()

    async def test_remove_file_nonexistent(self, handler: FSHandler):
        """Test removing nonexistent file"""
        with pytest.raises(FileNotFoundError, match="File not found"):
            await handler.remove_file("nonexistent.txt")

    async def test_list_files(self, handler: FSHandler, sample_file_content):
        """Test file listing"""
        # Create test files
        await handler.write_file(sample_file_content, ".", "file1.txt")
        await handler.write_file(sample_file_content, ".", "file2.txt")
        await handler.make_directory("subdir")

        files = await handler.list_files(".")
        assert "file1.txt" in files
        assert "file2.txt" in files
        assert "subdir" not in files  # Directories should not be listed

    async def test_list_files_nonexistent(self, handler: FSHandler):
        """Test listing files in nonexistent directory"""
        with pytest.raises(FileNotFoundError, match="Directory not found"):
            await handler.list_files("nonexistent")

    async def test_file_exists(self, handler: FSHandler, sample_file_content):
        """Test file existence check"""
        assert not await handler.file_exists("test_file.txt")

        await handler.write_file(sample_file_content, ".", "test_file.txt")
        assert await handler.file_exists("test_file.txt")

    async def test_file_exists_directory(self, handler: FSHandler):
        """Test file existence check on directory"""
        await handler.make_directory("test_dir")
        assert not await handler.file_exists(
            "test_dir"
        )  # Should return False for directories

    async def test_get_file_size(self, handler: FSHandler, sample_file_content):
        """Test file size retrieval"""
        await handler.write_file(sample_file_content, ".", "test_file.txt")

        size = await handler.get_file_size("test_file.txt")
        assert size == len(sample_file_content)

    async def test_get_file_size_nonexistent(self, handler: FSHandler):
        """Test file size retrieval for nonexistent file"""
        with pytest.raises(FileNotFoundError, match="File not found"):
            await handler.get_file_size("nonexistent.txt")

    async def test_async_concurrency(self, handler: FSHandler):
        """Test async concurrency of file operations"""

        async def write_file(filename, content):
            await handler.write_file(content, ".", filename)

        # Test concurrent file writes using asyncio
        tasks = []
        for i in range(10):
            content = f"Content {i}".encode()
            task = write_file(f"file_{i}.txt", content)
            tasks.append(task)

        # Wait for all to complete
        await asyncio.gather(*tasks)

        # Verify all files were written correctly
        for i in range(10):
            assert await handler.file_exists(f"file_{i}.txt")
            content = await handler.read_file(f"file_{i}.txt")
            assert content == f"Content {i}".encode()

    async def test_empty_path_validation(self, handler: FSHandler):
        """Test validation of empty paths"""
        with pytest.raises(ValueError, match="cannot be empty"):
            await handler.read_file("")

        with pytest.raises(ValueError, match="cannot be empty"):
            await handler.file_exists("")

        with pytest.raises(ValueError, match="cannot be empty"):
            await handler.get_file_size("")

    async def test_atomic_write_rollback(self, handler: FSHandler):
        """Test atomic write rollback on failure"""

        # Mock a failure during file write
        def failing_move(*args, **kwargs):
            raise OSError("Simulated failure")

        with patch("shutil.move", side_effect=failing_move):
            with pytest.raises(OSError, match="Simulated failure"):
                await handler.write_file(b"test content", ".", "test_file.txt")

        # Verify no temporary files are left behind
        temp_files = [f for f in await handler.list_files(".") if f.startswith(".tmp_")]
        assert len(temp_files) == 0

        # Verify the target file was not created
        assert not await handler.file_exists("test_file.txt")

    async def test_concurrent_directory_operations(self, handler: FSHandler):
        """Test concurrent directory operations"""

        async def create_and_remove_dir(dir_name):
            await handler.make_directory(dir_name)
            await handler.remove_directory(dir_name)

        # Test concurrent directory operations using asyncio
        tasks = []
        for i in range(5):
            task = create_and_remove_dir(f"test_dir_{i}")
            tasks.append(task)

        # Wait for all to complete
        await asyncio.gather(*tasks)

        # Verify all directories were cleaned up
        dirs = await handler.list_directories(".")
        for i in range(5):
            assert f"test_dir_{i}" not in dirs
