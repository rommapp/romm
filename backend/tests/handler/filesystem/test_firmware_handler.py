import binascii
import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest
from anyio import open_file

from config.config_manager import LIBRARY_BASE_PATH, Config
from exceptions.fs_exceptions import FirmwareNotFoundException
from handler.filesystem.firmware_handler import FSFirmwareHandler
from utils.hashing import crc32_to_hex


class TestFSFirmwareHandler:
    """Test suite for FSFirmwareHandler class"""

    @pytest.fixture
    def handler(self):
        return FSFirmwareHandler()

    @pytest.fixture
    def config(self):
        return Config(
            EXCLUDED_PLATFORMS=[],
            EXCLUDED_SINGLE_EXT=["tmp"],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={},
            PLATFORMS_VERSIONS={},
            ROMS_FOLDER_NAME="roms",
            FIRMWARE_FOLDER_NAME="bios",
        )

    def test_init_uses_library_base_path(self, handler: FSFirmwareHandler):
        """Test that FSFirmwareHandler initializes with LIBRARY_BASE_PATH"""
        assert handler.base_path == Path(LIBRARY_BASE_PATH).resolve()

    async def test_get_firmware(self, handler: FSFirmwareHandler, config):
        """Test get_firmware method"""
        platform_fs_slug = "n64"

        with patch(
            "handler.filesystem.firmware_handler.cm.get_config", return_value=config
        ):
            result = await handler.get_firmware(platform_fs_slug)
            assert "bios1.bin" in result
            assert "bios2.bin" in result
            assert "temp.tmp" not in result

        platform_fs_slug = "psx"

        with patch(
            "handler.filesystem.firmware_handler.cm.get_config", return_value=config
        ):
            result = await handler.get_firmware(platform_fs_slug)
            assert "scph1001.bin" in result

    async def test_get_firmware_nonexistent_platform(
        self, handler: FSFirmwareHandler, config
    ):
        """Test get_firmware method with nonexistent platform"""
        platform_fs_slug = "nonexistent"

        with patch(
            "handler.filesystem.firmware_handler.cm.get_config", return_value=config
        ):
            with pytest.raises(FirmwareNotFoundException):
                await handler.get_firmware(platform_fs_slug)

    async def test_calculate_file_hashes(self, handler: FSFirmwareHandler):
        """Test calculate_file_hashes method with actual file"""
        firmware_path = "n64/bios"
        file_name = "bios1.bin"

        result = await handler.calculate_file_hashes(firmware_path, file_name)

        assert isinstance(result, dict)
        assert "crc_hash" in result
        assert "md5_hash" in result
        assert "sha1_hash" in result

        assert isinstance(result["crc_hash"], str)
        assert isinstance(result["md5_hash"], str)
        assert isinstance(result["sha1_hash"], str)

        assert len(result["crc_hash"]) > 0
        assert len(result["md5_hash"]) > 0
        assert len(result["sha1_hash"]) > 0

        file_path = handler.base_path / firmware_path / file_name
        async with await open_file(file_path, "rb") as f:
            content = await f.read()

        crc_expected = crc32_to_hex(binascii.crc32(content))
        md5_expected = hashlib.md5(content, usedforsecurity=False).hexdigest()
        sha1_expected = hashlib.sha1(content, usedforsecurity=False).hexdigest()

        result = await handler.calculate_file_hashes(firmware_path, file_name)

        assert result["crc_hash"] == crc_expected
        assert result["md5_hash"] == md5_expected
        assert result["sha1_hash"] == sha1_expected

    async def test_calculate_file_hashes_different_files(
        self, handler: FSFirmwareHandler
    ):
        """Test calculate_file_hashes with different files have different hashes"""
        firmware_path = "n64/bios"

        result1 = await handler.calculate_file_hashes(firmware_path, "bios1.bin")
        result2 = await handler.calculate_file_hashes(firmware_path, "bios2.bin")

        # Different files should have different hashes
        assert result1["crc_hash"] != result2["crc_hash"]
        assert result1["md5_hash"] != result2["md5_hash"]
        assert result1["sha1_hash"] != result2["sha1_hash"]

    async def test_calculate_file_hashes_nonexistent_file(
        self, handler: FSFirmwareHandler
    ):
        """Test calculate_file_hashes with nonexistent file"""
        firmware_path = "n64/bios"
        file_name = "nonexistent.bin"

        with pytest.raises(FileNotFoundError):
            await handler.calculate_file_hashes(firmware_path, file_name)

    def test_integration_with_base_handler_methods(self, handler: FSFirmwareHandler):
        """Test that FSFirmwareHandler properly inherits from FSHandler"""
        # Test that handler has base methods
        assert hasattr(handler, "validate_path")
        assert hasattr(handler, "list_files")
        assert hasattr(handler, "file_exists")
        assert hasattr(handler, "move_file_or_folder")
        assert hasattr(handler, "stream_file")
        assert hasattr(handler, "exclude_single_files")

    def test_firmware_path_construction(self, handler: FSFirmwareHandler, config):
        """Test that firmware paths are constructed correctly"""
        platform_fs_slug = "n64"

        with patch(
            "handler.filesystem.firmware_handler.cm.get_config", return_value=config
        ):
            # Test normal path (high prio doesn't exist)
            path = handler.get_firmware_fs_structure(platform_fs_slug)
            assert path == f"{platform_fs_slug}/{config.FIRMWARE_FOLDER_NAME}"

    async def test_multiple_platform_handling(self, handler: FSFirmwareHandler, config):
        """Test handling of different platform slugs"""
        platforms = ["n64", "psx"]  # Use platforms that actually exist in test data

        with patch(
            "handler.filesystem.firmware_handler.cm.get_config", return_value=config
        ):
            for platform in platforms:
                path = handler.get_firmware_fs_structure(platform)
                assert platform in path
                assert config.FIRMWARE_FOLDER_NAME in path

                # Test that we can actually get firmware for existing platforms
                firmware_files = await handler.get_firmware(platform)
                assert len(firmware_files) > 0  # Should have at least one file

    async def test_exclude_single_files_integration(
        self, handler: FSFirmwareHandler, config
    ):
        """Test that exclude_single_files works with actual files"""
        platform_fs_slug = "n64"

        with patch(
            "handler.filesystem.firmware_handler.cm.get_config", return_value=config
        ):
            # Get all files in the directory
            firmware_path = handler.get_firmware_fs_structure(platform_fs_slug)
            all_files = await handler.list_files(path=firmware_path)

            # Should include .tmp files before exclusion
            assert "temp.tmp" in all_files
            assert "bios1.bin" in all_files
            assert "bios2.bin" in all_files

            # After exclusion, .tmp files should be removed
            filtered_files = handler.exclude_single_files(all_files)
            assert "temp.tmp" not in filtered_files
            assert "bios1.bin" in filtered_files
            assert "bios2.bin" in filtered_files

    async def test_file_operations_with_actual_structure(
        self, handler: FSFirmwareHandler
    ):
        """Test that file operations work with the actual directory structure"""
        # Test that we can list files
        n64_files = await handler.list_files("n64/bios")
        assert len(n64_files) > 0

        psx_files = await handler.list_files("psx/bios")
        assert len(psx_files) > 0

        # Test that we can check file existence
        assert await handler.file_exists("n64/bios/bios1.bin")
        assert await handler.file_exists("psx/bios/scph1001.bin")
        assert not await handler.file_exists("n64/bios/nonexistent.bin")

    async def test_stream_file_with_actual_files(self, handler: FSFirmwareHandler):
        """Test streaming actual files"""
        async with await handler.stream_file("n64/bios/bios1.bin") as f:
            content = await f.read()
            assert len(content) > 0
            assert b"This is a test N64 BIOS file 1" in content
