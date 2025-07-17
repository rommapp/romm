import hashlib
import shutil
import tempfile
from unittest.mock import Mock, patch

import pytest
from config.config_manager import Config
from exceptions.fs_exceptions import FirmwareAlreadyExistsException
from handler.filesystem.firmware_handler import FSFirmwareHandler


class TestFSFirmwareHandler:
    """Test suite for FSFirmwareHandler class"""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def handler(self, temp_dir):
        """Create FSFirmwareHandler instance for testing"""
        with patch("handler.filesystem.firmware_handler.LIBRARY_BASE_PATH", temp_dir):
            return FSFirmwareHandler()

    @pytest.fixture
    def config(self):
        return Config(
            EXCLUDED_PLATFORMS=[],
            EXCLUDED_SINGLE_EXT=[],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={},
            PLATFORMS_VERSIONS={},
            ROMS_FOLDER_NAME="roms",
            FIRMWARE_FOLDER_NAME="bios",
        )

    @pytest.fixture
    def sample_firmware_content(self):
        """Sample firmware content for testing"""
        return b"This is test firmware content for hashing and file operations"

    def test_init_uses_library_base_path(self, temp_dir):
        """Test that FSFirmwareHandler initializes with LIBRARY_BASE_PATH"""
        from pathlib import Path

        with patch("handler.filesystem.firmware_handler.LIBRARY_BASE_PATH", temp_dir):
            handler = FSFirmwareHandler()
            assert handler.base_path == Path(temp_dir).resolve()

    def test_get_firmware_fs_structure_high_prio_exists(self, handler, config):
        """Test get_firmware_fs_structure when high priority structure exists"""
        fs_slug = "ps2"

        with patch(
            "handler.filesystem.firmware_handler.cm.get_config", return_value=config
        ):
            with patch("os.path.exists", return_value=True):
                result = handler.get_firmware_fs_structure(fs_slug)
                expected = f"{config.FIRMWARE_FOLDER_NAME}/{fs_slug}"
                assert result == expected

    def test_get_firmware_fs_structure_high_prio_not_exists(self, handler, config):
        """Test get_firmware_fs_structure when high priority structure doesn't exist"""
        fs_slug = "ps2"

        with patch(
            "handler.filesystem.firmware_handler.cm.get_config", return_value=config
        ):
            with patch("os.path.exists", return_value=False):
                result = handler.get_firmware_fs_structure(fs_slug)
                expected = f"{fs_slug}/{config.FIRMWARE_FOLDER_NAME}"
                assert result == expected

    def test_get_firmware_success(self, handler, config):
        """Test get_firmware method with successful file listing"""
        platform_fs_slug = "n64"
        firmware_files = ["bios1.bin", "bios2.bin", "excluded.tmp"]
        filtered_files = ["bios1.bin", "bios2.bin"]

        with patch(
            "handler.filesystem.firmware_handler.cm.get_config", return_value=config
        ):
            with patch("os.path.exists", return_value=True):
                with patch.object(handler, "list_files", return_value=firmware_files):
                    with patch.object(
                        handler, "exclude_single_files", return_value=filtered_files
                    ):
                        result = handler.get_firmware(platform_fs_slug)
                        assert result == filtered_files

    def test_get_firmware_calls_correct_methods(self, handler, config):
        """Test that get_firmware calls the correct methods in sequence"""
        platform_fs_slug = "psx"
        firmware_files = ["bios.bin"]

        with patch(
            "handler.filesystem.firmware_handler.cm.get_config", return_value=config
        ):
            with patch("os.path.exists", return_value=True):
                with patch.object(
                    handler, "list_files", return_value=firmware_files
                ) as mock_list:
                    with patch.object(
                        handler, "exclude_single_files", return_value=firmware_files
                    ) as mock_exclude:
                        result = handler.get_firmware(platform_fs_slug)

                        # Verify the correct path was used
                        expected_path = (
                            f"{config.FIRMWARE_FOLDER_NAME}/{platform_fs_slug}"
                        )
                        mock_list.assert_called_once_with(path=expected_path)
                        mock_exclude.assert_called_once_with(firmware_files)
                        assert result == firmware_files

    def test_calculate_file_hashes(self, handler, sample_firmware_content):
        """Test calculate_file_hashes method"""
        firmware_path = "test_platform/bios"
        file_name = "test_bios.bin"

        # Create a mock file stream that supports context manager protocol
        mock_stream = Mock()
        mock_stream.read.side_effect = [
            sample_firmware_content,
            b"",
        ]  # First read returns content, second returns empty
        mock_stream.__enter__ = Mock(return_value=mock_stream)
        mock_stream.__exit__ = Mock(return_value=None)

        with patch.object(handler, "stream_file", return_value=mock_stream):
            result = handler.calculate_file_hashes(firmware_path, file_name)

            # Verify the structure of the result
            assert isinstance(result, dict)
            assert "crc_hash" in result
            assert "md5_hash" in result
            assert "sha1_hash" in result

            # Verify hash values are strings
            assert isinstance(result["crc_hash"], str)
            assert isinstance(result["md5_hash"], str)
            assert isinstance(result["sha1_hash"], str)

    def test_calculate_file_hashes_actual_values(
        self, handler, sample_firmware_content
    ):
        """Test calculate_file_hashes with actual hash verification"""
        firmware_path = "test_platform/bios"
        file_name = "test_bios.bin"

        # Calculate expected values
        import binascii

        from utils.hashing import crc32_to_hex

        crc_expected = crc32_to_hex(binascii.crc32(sample_firmware_content))
        md5_expected = hashlib.md5(
            sample_firmware_content, usedforsecurity=False
        ).hexdigest()
        sha1_expected = hashlib.sha1(
            sample_firmware_content, usedforsecurity=False
        ).hexdigest()

        # Create a mock file stream that supports context manager protocol
        mock_stream = Mock()
        mock_stream.read.side_effect = [sample_firmware_content, b""]
        mock_stream.__enter__ = Mock(return_value=mock_stream)
        mock_stream.__exit__ = Mock(return_value=None)

        with patch.object(handler, "stream_file", return_value=mock_stream):
            result = handler.calculate_file_hashes(firmware_path, file_name)

            assert result["crc_hash"] == crc_expected
            assert result["md5_hash"] == md5_expected
            assert result["sha1_hash"] == sha1_expected

    def test_calculate_file_hashes_chunked_reading(self, handler):
        """Test calculate_file_hashes with chunked reading"""
        firmware_path = "test_platform/bios"
        file_name = "test_bios.bin"

        # Create test data larger than chunk size
        chunk1 = b"A" * 4096
        chunk2 = b"B" * 4096
        chunk3 = b"C" * 1000

        # Create a mock file stream that returns chunks and supports context manager protocol
        mock_stream = Mock()
        mock_stream.read.side_effect = [chunk1, chunk2, chunk3, b""]
        mock_stream.__enter__ = Mock(return_value=mock_stream)
        mock_stream.__exit__ = Mock(return_value=None)

        with patch.object(handler, "stream_file", return_value=mock_stream):
            result = handler.calculate_file_hashes(firmware_path, file_name)

            # Verify that multiple reads were made
            assert mock_stream.read.call_count == 4

            # Verify results are still strings
            assert isinstance(result["crc_hash"], str)
            assert isinstance(result["md5_hash"], str)
            assert isinstance(result["sha1_hash"], str)

    def test_calculate_file_hashes_stream_file_called_correctly(self, handler):
        """Test that calculate_file_hashes calls stream_file with correct parameters"""
        firmware_path = "test_platform/bios"
        file_name = "test_bios.bin"

        mock_stream = Mock()
        mock_stream.read.side_effect = [b"test", b""]
        mock_stream.__enter__ = Mock(return_value=mock_stream)
        mock_stream.__exit__ = Mock(return_value=None)

        with patch.object(
            handler, "stream_file", return_value=mock_stream
        ) as mock_stream_method:
            handler.calculate_file_hashes(firmware_path, file_name)

            expected_file_path = f"{firmware_path}/{file_name}"
            mock_stream_method.assert_called_once_with(file_path=expected_file_path)

    def test_rename_file_same_name(self, handler):
        """Test rename_file when old and new names are the same"""
        old_name = "bios.bin"
        new_name = "bios.bin"
        file_path = "ps2/bios"

        # Should not call any file operations
        with patch.object(handler, "file_exists") as mock_exists:
            with patch.object(handler, "move_file") as mock_move:
                handler.rename_file(old_name, new_name, file_path)

                mock_exists.assert_not_called()
                mock_move.assert_not_called()

    def test_rename_file_different_name_success(self, handler):
        """Test rename_file when names are different and target doesn't exist"""
        old_name = "old_bios.bin"
        new_name = "new_bios.bin"
        file_path = "ps2/bios"

        with patch.object(handler, "file_exists", return_value=False):
            with patch.object(handler, "move_file") as mock_move:
                handler.rename_file(old_name, new_name, file_path)

                # The method reassigns file_path to include new_name
                modified_file_path = f"{file_path}/{new_name}"
                expected_source = f"{modified_file_path}/{old_name}"
                expected_dest = f"{modified_file_path}/{new_name}"
                mock_move.assert_called_once_with(
                    source_path=expected_source, dest_path=expected_dest
                )

    def test_rename_file_target_exists_raises_exception(self, handler):
        """Test rename_file raises exception when target file already exists"""
        old_name = "old_bios.bin"
        new_name = "existing_bios.bin"
        file_path = "ps2/bios"

        with patch.object(handler, "file_exists", return_value=True):
            with patch.object(handler, "move_file") as mock_move:
                with pytest.raises(FirmwareAlreadyExistsException):
                    handler.rename_file(old_name, new_name, file_path)

                mock_move.assert_not_called()

    def test_rename_file_file_exists_called_correctly(self, handler):
        """Test that rename_file calls file_exists with correct path"""
        old_name = "old_bios.bin"
        new_name = "new_bios.bin"
        file_path = "ps2/bios"

        with patch.object(handler, "file_exists", return_value=False) as mock_exists:
            with patch.object(handler, "move_file"):
                handler.rename_file(old_name, new_name, file_path)

                # The method reassigns file_path to include new_name before checking
                modified_file_path = f"{file_path}/{new_name}"
                mock_exists.assert_called_once_with(file_path=modified_file_path)

    def test_integration_with_base_handler_methods(self, handler):
        """Test that FSFirmwareHandler properly inherits from FSHandler"""
        # Test that handler has base methods
        assert hasattr(handler, "validate_path")
        assert hasattr(handler, "list_files")
        assert hasattr(handler, "file_exists")
        assert hasattr(handler, "move_file")
        assert hasattr(handler, "stream_file")
        assert hasattr(handler, "exclude_single_files")

    def test_firmware_path_construction(self, handler, config):
        """Test that firmware paths are constructed correctly"""
        platform_fs_slug = "dreamcast"

        with patch(
            "handler.filesystem.firmware_handler.cm.get_config", return_value=config
        ):
            # Test high priority path
            with patch("os.path.exists", return_value=True):
                path = handler.get_firmware_fs_structure(platform_fs_slug)
                assert path == f"{config.FIRMWARE_FOLDER_NAME}/{platform_fs_slug}"

            # Test normal path
            with patch("os.path.exists", return_value=False):
                path = handler.get_firmware_fs_structure(platform_fs_slug)
                assert path == f"{platform_fs_slug}/{config.FIRMWARE_FOLDER_NAME}"

    def test_error_handling_in_get_firmware(self, handler, config):
        """Test error handling in get_firmware method"""
        platform_fs_slug = "invalid_platform"

        with patch(
            "handler.filesystem.firmware_handler.cm.get_config", return_value=config
        ):
            with patch("os.path.exists", return_value=True):
                with patch.object(
                    handler,
                    "list_files",
                    side_effect=FileNotFoundError("Directory not found"),
                ):
                    with pytest.raises(FileNotFoundError):
                        handler.get_firmware(platform_fs_slug)

    def test_multiple_platform_handling(self, handler, config):
        """Test handling of different platform slugs"""
        platforms = ["ps1", "ps2", "n64", "dreamcast", "saturn"]

        with patch(
            "handler.filesystem.firmware_handler.cm.get_config", return_value=config
        ):
            with patch("os.path.exists", return_value=True):
                for platform in platforms:
                    path = handler.get_firmware_fs_structure(platform)
                    assert platform in path
                    assert config.FIRMWARE_FOLDER_NAME in path
