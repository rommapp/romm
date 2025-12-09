import os
import shutil
from pathlib import Path
from unittest.mock import Mock

import pytest

from config.config_manager import LIBRARY_BASE_PATH, Config
from handler.filesystem.roms_handler import (
    CHDHashWrapper,
    FileHash,
    FSRomsHandler,
    extract_chd_hash,
)
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory


class TestFSRomsHandler:
    """Test suite for FSRomsHandler class"""

    @pytest.fixture
    def handler(self):
        return FSRomsHandler()

    @pytest.fixture
    def config(self):
        return Config(
            EXCLUDED_PLATFORMS=[],
            EXCLUDED_SINGLE_EXT=["tmp"],
            EXCLUDED_SINGLE_FILES=["excluded_test.tmp"],
            EXCLUDED_MULTI_FILES=["excluded_multi"],
            EXCLUDED_MULTI_PARTS_EXT=["tmp"],
            EXCLUDED_MULTI_PARTS_FILES=["excluded_part.bin"],
            PLATFORMS_BINDING={},
            PLATFORMS_VERSIONS={},
            ROMS_FOLDER_NAME="roms",
            FIRMWARE_FOLDER_NAME="bios",
        )

    @pytest.fixture
    def platform(self):
        return Platform(name="Nintendo 64", slug="n64", fs_slug="n64")

    @pytest.fixture
    def rom_single(self, platform: Platform):
        return Rom(
            id=1,
            fs_name="Paper Mario (USA).z64",
            fs_path="n64/roms",
            platform=platform,
            full_path="n64/roms/Paper Mario (USA).z64",
        )

    @pytest.fixture
    def rom_single_nested(self, platform: Platform):
        return Rom(
            id=3,
            fs_name="Sonic (EU) [T]",
            fs_path="n64/roms",
            platform=platform,
            full_path="n64/roms/Sonic (EU) [T]",
            files=[
                RomFile(
                    id=1,
                    file_name="Sonic (EU) [T].n64",
                    file_path="n64/roms/Sonic (EU) [T]",
                ),
                RomFile(
                    id=2,
                    file_name="Sonic (EU) [T-En].z64",
                    file_path="n64/roms/Sonic (EU) [T]/translation",
                ),
            ],
        )

    @pytest.fixture
    def rom_multi(self, platform: Platform):
        return Rom(
            id=2,
            fs_name="Super Mario 64 (J) (Rev A)",
            fs_path="n64/roms",
            platform=platform,
            files=[
                RomFile(
                    id=1,
                    file_name="Super Mario 64 (J) (Rev A) [Part 1].z64",
                    file_path="n64/roms",
                ),
                RomFile(
                    id=2,
                    file_name="Super Mario 64 (J) (Rev A) [Part 2].z64",
                    file_path="n64/roms",
                ),
            ],
        )

    def test_init_uses_library_base_path(self, handler: FSRomsHandler):
        """Test that FSRomsHandler initializes with LIBRARY_BASE_PATH"""
        assert handler.base_path == Path(LIBRARY_BASE_PATH).resolve()

    def test_get_roms_fs_structure_normal_structure(self, handler: FSRomsHandler):
        """Test get_roms_fs_structure with normal structure"""
        fs_slug = "n64"

        with pytest.MonkeyPatch.context() as m:
            m.setattr(
                "handler.filesystem.roms_handler.cm.get_config",
                lambda: Config(
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
                ),
            )
            m.setattr("os.path.exists", lambda x: False)  # Simulate normal structure

            result = handler.get_roms_fs_structure(fs_slug)
            assert result == f"{fs_slug}/roms"

    def test_get_roms_fs_structure_high_priority_structure(
        self, handler: FSRomsHandler
    ):
        """Test get_roms_fs_structure with high priority structure"""
        fs_slug = "n64"

        with pytest.MonkeyPatch.context() as m:
            m.setattr(
                "handler.filesystem.roms_handler.cm.get_config",
                lambda: Config(
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
                ),
            )
            m.setattr(
                "os.path.exists", lambda x: True
            )  # Simulate high priority structure

            result = handler.get_roms_fs_structure(fs_slug)
            assert result == f"roms/{fs_slug}"

    def test_parse_tags_regions_and_languages(self, handler: FSRomsHandler):
        """Test parse_tags method with regions and languages"""
        fs_name = "Zelda (USA) (Rev 1) [En,Fr] [Test].n64"

        regions, revision, languages, other_tags = handler.parse_tags(fs_name)

        assert "USA" in regions
        assert revision == "1"
        assert "English" in languages
        assert "French" in languages
        assert "Test" in other_tags

    def test_parse_tags_complex_tags(self, handler: FSRomsHandler):
        """Test parse_tags with complex tag structures"""
        fs_name = "Game (Europe) (En,De,Fr,Es,It) (Rev A) [Reg-PAL] [Beta].rom"

        regions, revision, languages, other_tags = handler.parse_tags(fs_name)

        assert "Europe" in regions
        assert "PAL" in regions
        assert revision == "A"
        assert "English" in languages
        assert "German" in languages
        assert "French" in languages
        assert "Spanish" in languages
        assert "Italian" in languages
        assert "Beta" in other_tags

    def test_parse_tags_no_tags(self, handler: FSRomsHandler):
        """Test parse_tags with no tags"""
        fs_name = "Simple Game.rom"

        regions, revision, languages, other_tags = handler.parse_tags(fs_name)

        assert regions == []
        assert revision == ""
        assert languages == []
        assert other_tags == []

    def test_exclude_multi_roms_filters_excluded(self, handler: FSRomsHandler, config):
        """Test exclude_multi_roms filters out excluded multi-file ROMs"""
        roms = ["Game1", "excluded_multi", "Game2", "Game3"]

        with pytest.MonkeyPatch.context() as m:
            m.setattr("handler.filesystem.roms_handler.cm.get_config", lambda: config)

            result = handler.exclude_multi_roms(roms)
            expected = ["Game1", "Game2", "Game3"]

            assert result == expected

    def test_exclude_multi_roms_no_exclusions(self, handler: FSRomsHandler):
        """Test exclude_multi_roms with no exclusions"""
        roms = ["Game1", "Game2", "Game3"]
        config = Config(
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

        with pytest.MonkeyPatch.context() as m:
            m.setattr("handler.filesystem.roms_handler.cm.get_config", lambda: config)

            result = handler.exclude_multi_roms(roms)
            assert result == roms

    def test_build_rom_file_single_file(self, rom_single: Rom, handler: FSRomsHandler):
        """Test _build_rom_file with actual single ROM file"""
        rom_path = Path(rom_single.fs_path)
        file_name = rom_single.fs_name
        file_hash = FileHash(
            {
                "crc_hash": "ABCD1234",
                "md5_hash": "def456",
                "sha1_hash": "789ghi",
            }
        )

        rom_file = handler._build_rom_file(rom_single, rom_path, file_name, file_hash)

        assert isinstance(rom_file, RomFile)
        assert rom_file.file_name == file_name
        assert rom_file.file_path == str(rom_path)
        assert rom_file.crc_hash == "ABCD1234"
        assert rom_file.md5_hash == "def456"
        assert rom_file.sha1_hash == "789ghi"
        assert rom_file.file_size_bytes > 0  # Should have actual file size
        assert rom_file.last_modified is not None
        assert rom_file.category is None  # No category matching for this path

    def test_build_rom_file_with_category(self, rom_multi: Rom, handler: FSRomsHandler):
        """Test _build_rom_file with category detection"""
        # Test with DLC category
        rom_path = Path(rom_multi.fs_path, "dlc")
        file_name = "test_dlc.n64"
        file_hash = FileHash(
            {
                "crc_hash": "12345678",
                "md5_hash": "abcdef",
                "sha1_hash": "123456",
            }
        )

        # Create the test file
        os.makedirs(handler.base_path / rom_path, exist_ok=True)
        test_file = handler.base_path / rom_path / file_name
        test_file.write_text("Test DLC content")

        try:
            rom_file = handler._build_rom_file(
                rom_multi, rom_path, file_name, file_hash
            )

            assert rom_file.category == RomFileCategory.DLC
            assert rom_file.file_name == file_name
            assert rom_file.file_size_bytes > 0
        finally:
            # Clean up
            if test_file.exists():
                test_file.unlink()

    @pytest.mark.asyncio
    async def test_get_roms(self, handler: FSRomsHandler, platform, config):
        """Test get_roms with actual files in the filesystem"""
        with pytest.MonkeyPatch.context() as m:
            m.setattr("handler.filesystem.roms_handler.cm.get_config", lambda: config)
            m.setattr("os.path.exists", lambda x: False)  # Normal structure

            result = await handler.get_roms(platform)

            assert isinstance(result, list)
            assert len(result) > 0

            # Check that we have both single and multi ROMs
            single_roms = [r for r in result if not r["flat"]]
            multi_roms = [r for r in result if r["nested"]]

            assert len(single_roms) > 0
            assert len(multi_roms) > 0

            # Check specific files exist
            rom_names = [r["fs_name"] for r in result]
            assert "Paper Mario (USA).z64" in rom_names
            assert "Super Mario 64 (J) (Rev A)" in rom_names
            assert "Zelda (USA) (Rev 1) [En,Fr] [Test].n64" in rom_names

            # Check excluded files are not present
            assert "excluded_test.tmp" not in rom_names

    @pytest.mark.asyncio
    async def test_get_rom_files_single_rom(
        self, handler: FSRomsHandler, rom_single, config
    ):
        """Test get_rom_files with a single ROM file"""
        with pytest.MonkeyPatch.context() as m:
            m.setattr("handler.filesystem.roms_handler.cm.get_config", lambda: config)
            m.setattr("os.path.exists", lambda x: False)  # Normal structure

            rom_files, crc_hash, md5_hash, sha1_hash, ra_hash = (
                await handler.get_rom_files(rom_single)
            )

            assert len(rom_files) == 1
            assert isinstance(rom_files[0], RomFile)
            assert rom_files[0].file_name == "Paper Mario (USA).z64"
            assert rom_files[0].file_path == "n64/roms"
            assert rom_files[0].file_size_bytes > 0

            assert crc_hash == "efb5af2e"
            assert md5_hash == "0f343b0931126a20f133d67c2b018a3b"
            assert sha1_hash == "60cacbf3d72e1e7834203da608037b1bf83b40e8"

    @pytest.mark.asyncio
    async def test_get_rom_files_multi_rom(
        self, handler: FSRomsHandler, rom_multi, config
    ):
        """Test get_rom_files with a multi-part ROM"""
        with pytest.MonkeyPatch.context() as m:
            m.setattr("handler.filesystem.roms_handler.cm.get_config", lambda: config)
            m.setattr("os.path.exists", lambda x: False)  # Normal structure

            rom_files, crc_hash, md5_hash, sha1_hash, ra_hash = (
                await handler.get_rom_files(rom_multi)
            )

            assert len(rom_files) >= 2  # Should have multiple parts

            file_names = [rf.file_name for rf in rom_files]
            assert "Super Mario 64 (J) (Rev A) [Part 1].z64" in file_names
            assert "Super Mario 64 (J) (Rev A) [Part 2].z64" in file_names

            for rom_file in rom_files:
                assert isinstance(rom_file, RomFile)
                assert rom_file.file_size_bytes > 0
                assert rom_file.last_modified is not None

    async def test_rename_fs_rom_same_name(self, handler: FSRomsHandler):
        """Test rename_fs_rom when old and new names are the same"""
        old_name = "test_rom.n64"
        new_name = "test_rom.n64"
        fs_path = "n64/roms"

        # Should not raise any exception
        await handler.rename_fs_rom(old_name, new_name, fs_path)

    async def test_rename_fs_rom_different_name_target_exists(
        self, handler: FSRomsHandler
    ):
        """Test rename_fs_rom when target file already exists"""
        old_name = "Paper Mario (USA).z64"
        new_name = "test_game.n64"  # This file exists
        fs_path = "n64/roms"

        from exceptions.fs_exceptions import RomAlreadyExistsException

        with pytest.raises(RomAlreadyExistsException):
            await handler.rename_fs_rom(old_name, new_name, fs_path)

    async def test_rename_fs_rom_successful_rename(self, handler: FSRomsHandler):
        """Test successful ROM file rename"""
        # Create a test file to rename
        test_file = handler.base_path / "n64/roms/test_rename.n64"
        test_file.write_text("Test ROM content")

        old_name = "test_rename.n64"
        new_name = "renamed_rom.n64"
        fs_path = "n64/roms"

        try:
            await handler.rename_fs_rom(old_name, new_name, fs_path)

            # Check that old file is gone and new file exists
            old_path = handler.base_path / fs_path / old_name
            new_path = handler.base_path / fs_path / new_name

            assert not old_path.exists()
            assert new_path.exists()
            assert new_path.read_text() == "Test ROM content"
        finally:
            # Clean up
            new_path = handler.base_path / fs_path / new_name
            if new_path.exists():
                new_path.unlink()

    def test_integration_with_base_handler_methods(self, handler: FSRomsHandler):
        """Test that FSRomsHandler properly inherits from FSHandler"""
        # Test that handler has base methods
        assert hasattr(handler, "validate_path")
        assert hasattr(handler, "list_files")
        assert hasattr(handler, "list_directories")
        assert hasattr(handler, "file_exists")
        assert hasattr(handler, "move_file_or_folder")
        assert hasattr(handler, "stream_file")
        assert hasattr(handler, "exclude_single_files")

    async def test_exclude_single_files_integration(
        self, handler: FSRomsHandler, config
    ):
        """Test that exclude_single_files works with actual ROM files"""
        with pytest.MonkeyPatch.context() as m:
            m.setattr("handler.filesystem.roms_handler.cm.get_config", lambda: config)

            # Get all files in the ROM directory
            all_files = await handler.list_files(path="n64/roms")

            # Should include .tmp files before exclusion
            assert "excluded_test.tmp" in all_files
            assert "Paper Mario (USA).z64" in all_files

            # After exclusion, .tmp files should be removed
            filtered_files = handler.exclude_single_files(all_files)
            assert "excluded_test.tmp" not in filtered_files
            assert "Paper Mario (USA).z64" in filtered_files

    async def test_file_operations_with_actual_structure(self, handler: FSRomsHandler):
        """Test that file operations work with the actual ROM directory structure"""
        # Test that we can list files
        n64_files = await handler.list_files("n64/roms")
        assert len(n64_files) > 0

        n64_dirs = await handler.list_directories("n64/roms")
        assert len(n64_dirs) > 0

        # Test that we can check file existence
        assert await handler.file_exists("n64/roms/Paper Mario (USA).z64")
        assert await handler.file_exists("n64/roms/test_game.n64")
        assert not await handler.file_exists("n64/roms/nonexistent.rom")

    async def test_stream_file_with_actual_roms(self, handler: FSRomsHandler):
        """Test streaming actual ROM files"""
        async with await handler.stream_file("n64/roms/Paper Mario (USA).z64") as f:
            content = await f.read()
            assert len(content) > 0

        async with await handler.stream_file("n64/roms/test_game.n64") as f:
            content = await f.read()
            assert len(content) > 0
            assert b"Test N64 ROM" in content

    def test_tag_parsing_edge_cases(self, handler: FSRomsHandler):
        """Test tag parsing with edge cases"""
        # Test with comma-separated tags
        regions, revision, languages, other_tags = handler.parse_tags(
            "Game (USA,Europe) [En,Fr,De].rom"
        )
        assert "USA" in regions
        assert "Europe" in regions
        assert "English" in languages
        assert "French" in languages
        assert "German" in languages

        # Test with reg- prefix
        regions, revision, languages, other_tags = handler.parse_tags(
            "Game [Reg-NTSC].rom"
        )
        assert "NTSC" in regions

        # Test with rev- prefix
        regions, revision, languages, other_tags = handler.parse_tags(
            "Game [Rev-B].rom"
        )
        assert revision == "B"

    def test_platform_specific_behavior(self, handler: FSRomsHandler):
        """Test platform-specific behavior differences"""
        # Create mock platforms - one hashable, one non-hashable
        hashable_platform = Mock(spec=Platform)
        hashable_platform.fs_slug = "gba"
        hashable_platform.slug = "gba"

        non_hashable_platform = Mock(spec=Platform)
        non_hashable_platform.fs_slug = "n64"
        non_hashable_platform.slug = "nintendo-64"

        # Test ROM file structure paths
        hashable_path = handler.get_roms_fs_structure(hashable_platform.fs_slug)
        non_hashable_path = handler.get_roms_fs_structure(non_hashable_platform.fs_slug)

        with pytest.MonkeyPatch.context() as m:
            m.setattr("os.path.exists", lambda x: False)  # Normal structure

            assert hashable_path == f"{hashable_platform.fs_slug}/roms"
            assert non_hashable_path == f"{non_hashable_platform.fs_slug}/roms"

    async def test_multi_rom_directory_handling(self, handler: FSRomsHandler, config):
        """Test handling of multi-ROM directories with actual structure"""
        with pytest.MonkeyPatch.context() as m:
            m.setattr("handler.filesystem.roms_handler.cm.get_config", lambda: config)

            # List directories in the ROM path
            directories = await handler.list_directories("n64/roms")

            # Should include our multi-ROM directories
            assert "Super Mario 64 (J) (Rev A)" in directories
            assert "Test Multi Rom [USA]" in directories

            # After exclusion, normal directories should remain
            filtered_dirs = handler.exclude_multi_roms(directories)
            assert "Super Mario 64 (J) (Rev A)" in filtered_dirs
            assert "Test Multi Rom [USA]" in filtered_dirs

    def test_rom_fs_structure_consistency(self, handler: FSRomsHandler):
        """Test that ROM filesystem structure is consistent across methods"""
        fs_slug = "gba"

        with pytest.MonkeyPatch.context() as m:
            # Test with normal structure
            m.setattr("os.path.exists", lambda x: False)

            structure = handler.get_roms_fs_structure(fs_slug)
            assert structure == f"{fs_slug}/roms"

            # Test with high priority structure
            m.setattr("os.path.exists", lambda x: True)

            structure = handler.get_roms_fs_structure(fs_slug)
            assert structure == f"roms/{fs_slug}"

    def test_actual_file_hash_calculation(self, handler: FSRomsHandler):
        """Test hash calculation with actual files"""
        # Create a test file with known content for hash verification
        test_content = b"Test ROM content for hashing"
        test_file = handler.base_path / "n64/roms/hash_test.n64"
        test_file.write_bytes(test_content)

        try:
            # Calculate expected hashes
            import binascii
            import hashlib

            expected_crc = binascii.crc32(test_content)
            expected_md5 = hashlib.md5(test_content, usedforsecurity=False).hexdigest()
            expected_sha1 = hashlib.sha1(
                test_content, usedforsecurity=False
            ).hexdigest()

            # Test the hash calculation method
            crc_result, _, md5_result, _, sha1_result, _ = (
                handler._calculate_rom_hashes(
                    test_file,
                    0,
                    hashlib.md5(usedforsecurity=False),
                    hashlib.sha1(usedforsecurity=False),
                )
            )

            assert crc_result == expected_crc
            assert md5_result.hexdigest() == expected_md5
            assert sha1_result.hexdigest() == expected_sha1

        finally:
            # Clean up
            if test_file.exists():
                test_file.unlink()

    async def test_compressed_file_handling(self, handler: FSRomsHandler):
        """Test handling of compressed ROM files"""
        # Test with the ZIP file
        psx_files = await handler.list_files("psx/roms")
        assert "PaRappa the Rapper.zip" in psx_files

        # Verify we can stream the compressed file
        async with await handler.stream_file("psx/roms/PaRappa the Rapper.zip") as f:
            content = await f.read()
            assert len(content) > 0

    async def test_top_level_files_only_in_main_hash(
        self, handler: FSRomsHandler, rom_single_nested
    ):
        """Test that only top-level files contribute to main ROM hash calculation"""
        rom_files, rom_crc, rom_md5, rom_sha1, rom_ra = await handler.get_rom_files(
            rom_single_nested
        )

        # Verify we have multiple files (base game + translation)
        assert len(rom_files) == 2

        base_game_rom_file = None
        translation_rom_file = None

        for rom_file in rom_files:
            if rom_file.file_name == "Sonic (EU) [T].n64":
                base_game_rom_file = rom_file
            elif rom_file.file_name == "Sonic (EU) [T-En].z64":
                translation_rom_file = rom_file

        assert base_game_rom_file is not None, "Base game file not found"
        assert translation_rom_file is not None, "Translation file not found"

        # Verify file categories
        assert base_game_rom_file.category is None
        assert translation_rom_file.category == RomFileCategory.TRANSLATION

        # The main ROM hash should be different from the translation file hash
        # (this verifies that the translation is not included in the main hash)

        assert (
            rom_md5 == base_game_rom_file.md5_hash
        ), "Main ROM hash should include base game file"
        assert (
            rom_md5 != translation_rom_file.md5_hash
        ), "Main ROM hash should not include translation file"

        assert (
            rom_sha1 == base_game_rom_file.sha1_hash
        ), "Main ROM hash should include base game file"
        assert (
            rom_sha1 != translation_rom_file.sha1_hash
        ), "Main ROM hash should not include translation file"

    @pytest.mark.asyncio
    async def test_get_rom_files_with_chd_v5_uses_internal_hash(
        self, handler: FSRomsHandler, platform, tmp_path
    ):
        """Test that a CHD v5 file uses its internal hash and skips other hashing.

        This integration test verifies the complete CHD v5 hashing logic:
        1. For valid CHD v5 files, the embedded SHA1 hash from the file header is used
        2. CRC32 and MD5 hashes are NOT calculated from file contents
        3. The file is not double-processed by read_basic_file
        4. This prevents regressions in the if/elif archive type chain
        """
        # Create a mock CHD v5 file in a temporary directory
        chd_file = tmp_path / "test.chd"
        header = bytearray(124)
        header[0:8] = b"MComprHD"
        header[12:16] = int(5).to_bytes(4, "big")
        internal_sha1 = "0123456789abcdef0123456789abcdef01234567"
        header[84:104] = bytes.fromhex(internal_sha1)
        chd_file.write_bytes(
            header + b"This is extra file data to ensure file is not empty"
        )

        # Set up handler and rom object to point to the mock file
        roms_path = tmp_path / platform.fs_slug / "roms"
        roms_path.mkdir(parents=True)
        shutil.copy(chd_file, roms_path / "test.chd")

        # Create a new handler instance with temp base path
        test_handler = FSRomsHandler()
        test_handler.base_path = tmp_path

        rom = Rom(
            id=1,
            fs_name="test.chd",
            fs_path=str(roms_path.relative_to(tmp_path)),
            platform=platform,
        )

        # Run the hashing process
        rom_files, crc_hash, md5_hash, sha1_hash, _ = await test_handler.get_rom_files(
            rom
        )

        # Assert that only SHA1 is populated, and it's from the header
        assert len(rom_files) == 1
        assert sha1_hash == internal_sha1, "SHA1 should be from CHD v5 header"
        assert rom_files[0].sha1_hash == internal_sha1

        # CRC32 and MD5 should be empty/zero (not calculated)
        assert crc_hash == "", f"CRC hash should be empty, got: {crc_hash}"
        assert md5_hash == "", f"MD5 hash should be empty, got: {md5_hash}"
        assert rom_files[0].crc_hash == ""
        assert rom_files[0].md5_hash == ""

    @pytest.mark.asyncio
    async def test_get_rom_files_with_non_v5_chd_fallback_to_std_hashing(
        self, handler: FSRomsHandler, platform, tmp_path
    ):
        """Test that non-v5 CHD files fall back to standard file hashing.

        This ensures backward compatibility: if a .chd file is not version 5
        or doesn't have a valid v5 header, it should be treated as a regular
        file and all hashes (CRC32, MD5, SHA1) are calculated from content.
        """
        # Create a CHD v4 file (should not use internal hash logic)
        chd_file = tmp_path / "old_format.chd"
        header = bytearray(124)
        header[0:8] = b"MComprHD"
        header[12:16] = int(4).to_bytes(4, "big")  # Version 4, not 5

        # Add some content
        content = header + b"This is CHD v4 data that should be hashed as a normal file"
        chd_file.write_bytes(content)

        # Set up handler and rom object
        roms_path = tmp_path / platform.fs_slug / "roms"
        roms_path.mkdir(parents=True)
        shutil.copy(chd_file, roms_path / "old_format.chd")

        test_handler = FSRomsHandler()
        test_handler.base_path = tmp_path

        rom = Rom(
            id=1,
            fs_name="old_format.chd",
            fs_path=str(roms_path.relative_to(tmp_path)),
            platform=platform,
        )

        # Run the hashing process
        rom_files, crc_hash, md5_hash, sha1_hash, _ = await test_handler.get_rom_files(
            rom
        )

        # All hashes should be populated (calculated from file content)
        assert len(rom_files) == 1
        assert crc_hash != "", "CRC hash should be calculated for non-v5 CHD"
        assert md5_hash != "", "MD5 hash should be calculated for non-v5 CHD"
        assert sha1_hash != "", "SHA1 hash should be calculated for non-v5 CHD"

        # Verify they're actual hash values (not from an internal header)
        assert rom_files[0].crc_hash == crc_hash
        assert rom_files[0].md5_hash == md5_hash
        assert rom_files[0].sha1_hash == sha1_hash


class TestExtractCHDHash:
    """Test suite for extract_chd_hash function"""

    def test_extract_chd_hash_v5_valid(self, tmp_path):
        """Test extracting hash from a valid CHD v5 file"""
        chd_file = tmp_path / "test_v5.chd"

        # CHD v5 header structure (124 bytes minimum):
        # Bytes 0-7: "MComprHD" magic signature
        # Bytes 12-15: Version (5 in big-endian)
        # Bytes 84-103: SHA1 hash (20 bytes)
        header = bytearray(124)
        header[0:8] = b"MComprHD"
        header[12:16] = int(5).to_bytes(4, "big")
        # Use a test SHA1 hash
        header[84:104] = bytes.fromhex("0123456789abcdef0123456789abcdef01234567")

        chd_file.write_bytes(header)

        result = extract_chd_hash(chd_file)

        assert result is not None
        assert isinstance(result, str)
        assert len(result) == 40  # SHA1 hex is 40 characters
        assert result == "0123456789abcdef0123456789abcdef01234567"

    def test_extract_chd_hash_v1_rejected(self, tmp_path):
        """Test that CHD v1 files are rejected"""
        chd_file = tmp_path / "test_v1.chd"

        header = bytearray(124)
        header[0:8] = b"MComprHD"
        header[12:16] = int(1).to_bytes(4, "big")  # Version 1

        chd_file.write_bytes(header)

        result = extract_chd_hash(chd_file)

        assert result is None

    def test_extract_chd_hash_v2_rejected(self, tmp_path):
        """Test that CHD v2 files are rejected"""
        chd_file = tmp_path / "test_v2.chd"

        header = bytearray(124)
        header[0:8] = b"MComprHD"
        header[12:16] = int(2).to_bytes(4, "big")  # Version 2

        chd_file.write_bytes(header)

        result = extract_chd_hash(chd_file)

        assert result is None

    def test_extract_chd_hash_v3_rejected(self, tmp_path):
        """Test that CHD v3 files are rejected"""
        chd_file = tmp_path / "test_v3.chd"

        header = bytearray(124)
        header[0:8] = b"MComprHD"
        header[12:16] = int(3).to_bytes(4, "big")  # Version 3

        chd_file.write_bytes(header)

        result = extract_chd_hash(chd_file)

        assert result is None

    def test_extract_chd_hash_v4_rejected(self, tmp_path):
        """Test that CHD v4 files are rejected"""
        chd_file = tmp_path / "test_v4.chd"

        header = bytearray(124)
        header[0:8] = b"MComprHD"
        header[12:16] = int(4).to_bytes(4, "big")  # Version 4

        chd_file.write_bytes(header)

        result = extract_chd_hash(chd_file)

        assert result is None

    def test_extract_chd_hash_invalid_magic(self, tmp_path):
        """Test that files without CHD magic signature are rejected"""
        chd_file = tmp_path / "invalid_magic.bin"

        header = bytearray(124)
        header[0:8] = b"BadMagic"  # Not "MComprHD"
        header[12:16] = int(5).to_bytes(4, "big")

        chd_file.write_bytes(header)

        result = extract_chd_hash(chd_file)

        assert result is None

    def test_extract_chd_hash_truncated_header(self, tmp_path):
        """Test that CHD v5 file with truncated header is rejected"""
        chd_file = tmp_path / "truncated.chd"

        # Only write 100 bytes instead of required 124
        header = bytearray(100)
        header[0:8] = b"MComprHD"
        header[12:16] = int(5).to_bytes(4, "big")

        chd_file.write_bytes(header)

        result = extract_chd_hash(chd_file)

        assert result is None

    def test_extract_chd_hash_nonexistent_file(self, tmp_path):
        """Test that non-existent files are handled gracefully"""
        nonexistent = tmp_path / "does_not_exist.chd"

        result = extract_chd_hash(nonexistent)

        assert result is None

    def test_extract_chd_hash_empty_file(self, tmp_path):
        """Test that empty files are rejected"""
        chd_file = tmp_path / "empty.chd"
        chd_file.write_bytes(b"")

        result = extract_chd_hash(chd_file)

        assert result is None

    def test_extract_chd_hash_sha1_format(self, tmp_path):
        """Test that SHA1 hash is correctly formatted as hex"""
        chd_file = tmp_path / "test_format.chd"

        header = bytearray(124)
        header[0:8] = b"MComprHD"
        header[12:16] = int(5).to_bytes(4, "big")

        # Use a known SHA1 value
        test_sha1 = bytes.fromhex("356a192b7913b04c54574d18c28d46e6395428ab")
        header[84:104] = test_sha1

        chd_file.write_bytes(header)

        result = extract_chd_hash(chd_file)

        assert result == "356a192b7913b04c54574d18c28d46e6395428ab"
        # Verify it's lowercase hex
        assert result == result.lower()
        # Verify it's 40 characters (SHA1 is 20 bytes = 40 hex chars)
        assert len(result) == 40

    def test_extract_chd_hash_with_wrapper(self, tmp_path):
        """Test that extracted hash integrates properly with CHDHashWrapper"""
        chd_file = tmp_path / "test_wrapper.chd"

        header = bytearray(124)
        header[0:8] = b"MComprHD"
        header[12:16] = int(5).to_bytes(4, "big")
        test_sha1 = bytes.fromhex("0123456789abcdef0123456789abcdef01234567")
        header[84:104] = test_sha1

        chd_file.write_bytes(header)

        extracted_hash = extract_chd_hash(chd_file)
        assert extracted_hash is not None

        # Should be usable with CHDHashWrapper
        wrapper = CHDHashWrapper(extracted_hash, "sha1")
        assert wrapper.hexdigest() == extracted_hash
        assert len(wrapper.digest()) == 20
        # Verify digest bytes match the original
        assert wrapper.digest() == test_sha1

    def test_extract_chd_hash_unknown_version(self, tmp_path):
        """Test that unknown CHD versions are rejected"""
        chd_file = tmp_path / "test_unknown.chd"

        header = bytearray(124)
        header[0:8] = b"MComprHD"
        header[12:16] = int(99).to_bytes(4, "big")  # Unknown version

        chd_file.write_bytes(header)

        result = extract_chd_hash(chd_file)

        assert result is None

    def test_extract_chd_hash_multiple_different_hashes(self, tmp_path):
        """Test that different SHA1 hashes are correctly extracted"""
        test_cases = [
            "0000000000000000000000000000000000000000",
            "ffffffffffffffffffffffffffffffffffffffff",
            "356a192b7913b04c54574d18c28d46e6395428ab",
            "da39a3ee5e6b4b0d3255bfef95601890afd80709",
        ]

        for i, test_hash in enumerate(test_cases):
            chd_file = tmp_path / f"test_hash_{i}.chd"

            header = bytearray(124)
            header[0:8] = b"MComprHD"
            header[12:16] = int(5).to_bytes(4, "big")
            header[84:104] = bytes.fromhex(test_hash)

            chd_file.write_bytes(header)

            result = extract_chd_hash(chd_file)

            assert result == test_hash, f"Hash mismatch for test case {i}"

    def test_extract_chd_hash_version_boundary_cases(self, tmp_path):
        """Test version checking at boundaries (0, 1, 4, 5, 6)"""
        test_versions = [
            (0, None),  # Version 0 should return None
            (1, None),  # Version 1 should return None
            (4, None),  # Version 4 should return None
            (5, "0123456789abcdef0123456789abcdef01234567"),  # Version 5 should work
            (6, None),  # Version 6 should return None
        ]

        for version, expected in test_versions:
            chd_file = tmp_path / f"test_v{version}.chd"

            header = bytearray(124)
            header[0:8] = b"MComprHD"
            header[12:16] = int(version).to_bytes(4, "big")
            header[84:104] = bytes.fromhex("0123456789abcdef0123456789abcdef01234567")

            chd_file.write_bytes(header)

            result = extract_chd_hash(chd_file)

            if expected is None:
                assert result is None, f"Version {version} should return None"
            else:
                assert result == expected, f"Version {version} should return {expected}"

    def test_extract_chd_hash_file_too_short_for_magic(self, tmp_path):
        """Test file that's too short to even contain magic + version"""
        chd_file = tmp_path / "too_short.chd"

        # Only 8 bytes - has magic but no version
        header = bytearray(8)
        header[0:8] = b"MComprHD"

        chd_file.write_bytes(header)

        result = extract_chd_hash(chd_file)

        assert result is None

    def test_extract_chd_hash_permission_error(self, tmp_path):
        """Test graceful handling of permission errors"""
        chd_file = tmp_path / "no_read_permission.chd"

        header = bytearray(124)
        header[0:8] = b"MComprHD"
        header[12:16] = int(5).to_bytes(4, "big")

        chd_file.write_bytes(header)

        # Remove read permissions
        chd_file.chmod(0o000)

        try:
            result = extract_chd_hash(chd_file)
            assert result is None
        finally:
            # Restore permissions for cleanup
            chd_file.chmod(0o644)

    def test_extract_chd_hash_real_header(self, tmp_path):
        """Test extracting hash from real Pebble Beach Golf Links CHD v5 header

        This uses the actual 128-byte header from:
        Pebble Beach Golf Links - Stadler ni Chousen (Japan).chd

        Header bytes (hex):
        00000000: 4d43 6f6d 7072 4844 0000 007c 0000 0005  MComprHD...|....
        00000010: 6364 6c7a 6364 7a6c 6364 666c 0000 0000  cdlzcdzlcdfl....
        00000020: 0000 0000 1a97 4e00 0000 0000 1119 b3d0  ......N.........
        00000030: 0000 0000 0000 007c 0000 4c80 0000 0990  .......|..L.....
        00000040: 8389 486c 34df 316d 1fd3 3997 a3ef ce8c  ..Hl4.1m..9.....
        00000050: e9c9 6008 0167 fc76 f9e4 312e 6ab4 8fe9  ..`..g.v..1.j...
        00000060: 80d2 ce5b 23f7 75c2 0000 0000 0000 0000  ...[#.u.........
        00000070: 0000 0000 0000 0000 0000 0000 4348 5432  ............CHT2

        The SHA1 hash (combined raw+meta) at bytes 84-103 is:
        0167 fc76 f9e4 312e 6ab4 8fe9 80d2 ce5b 23f7 75c2
        """
        chd_file = tmp_path / "Pebble Beach.chd"

        # Real 128-byte header from the file
        real_header = bytes.fromhex(
            "4d43 6f6d 7072 4844 0000 007c 0000 0005 "
            "6364 6c7a 6364 7a6c 6364 666c 0000 0000 "
            "0000 0000 1a97 4e00 0000 0000 1119 b3d0 "
            "0000 0000 0000 007c 0000 4c80 0000 0990 "
            "8389 486c 34df 316d 1fd3 3997 a3ef ce8c "
            "e9c9 6008 0167 fc76 f9e4 312e 6ab4 8fe9 "
            "80d2 ce5b 23f7 75c2 0000 0000 0000 0000 "
            "0000 0000 0000 0000 0000 0000 4348 5432"
        )

        chd_file.write_bytes(real_header)

        result = extract_chd_hash(chd_file)

        # Expected SHA1 from the header at bytes 84-103 (20 bytes, as per chd.h)
        expected_sha1 = "0167fc76f9e4312e6ab48fe980d2ce5b23f775c2"

        assert result is not None
        assert result == expected_sha1
        assert len(result) == 40
        # Verify it matches what's in the header
        assert bytes.fromhex(result) == real_header[84:104]

    def test_extract_chd_hash_with_extra_metadata(self, tmp_path):
        """Test CHD v5 file with additional metadata beyond header

        Real CHD files often have map data and metadata after the 124-byte header.
        The hash extraction should work correctly regardless of file size.
        """
        chd_file = tmp_path / "test_with_metadata.chd"

        header = bytearray(124)
        header[0:8] = b"MComprHD"
        header[12:16] = int(5).to_bytes(4, "big")
        test_sha1 = bytes.fromhex("0167fc76f9e4312e6ab48fe980d2ce5b23f775c2")
        header[84:104] = test_sha1

        # Write header plus extra data (simulating map and metadata)
        extra_data = b"MAP_DATACOMPRESSED_DATA_GOES_HERE" * 100

        chd_file.write_bytes(header + extra_data)

        result = extract_chd_hash(chd_file)

        assert result is not None
        assert result == "0167fc76f9e4312e6ab48fe980d2ce5b23f775c2"
        assert bytes.fromhex(result) == test_sha1

    def test_extract_chd_hash_off_by_one_header_sizes(self, tmp_path):
        """Test boundary conditions around minimum required header size (104 bytes)"""
        test_cases = [
            (103, None),  # 103 bytes - not enough for SHA1 region
            (
                104,
                "0167fc76f9e4312e6ab48fe980d2ce5b23f775c2",
            ),  # 104 bytes - exactly enough
            (123, "0167fc76f9e4312e6ab48fe980d2ce5b23f775c2"),  # 123 bytes
            (124, "0167fc76f9e4312e6ab48fe980d2ce5b23f775c2"),  # Full v5 header
            (125, "0167fc76f9e4312e6ab48fe980d2ce5b23f775c2"),  # Extra byte
        ]

        for size, expected in test_cases:
            chd_file = tmp_path / f"test_size_{size}.chd"

            header = bytearray(size)
            header[0:8] = b"MComprHD"
            header[12:16] = int(5).to_bytes(4, "big")
            if size >= 104:
                header[84:104] = bytes.fromhex(
                    "0167fc76f9e4312e6ab48fe980d2ce5b23f775c2"
                )

            chd_file.write_bytes(header)

            result = extract_chd_hash(chd_file)

            assert (
                result == expected
            ), f"Failed for size {size}: got {result}, expected {expected}"

    def test_extract_chd_hash_corrupted_header_data(self, tmp_path):
        """Test handling of corrupted/invalid data in header fields"""
        chd_file = tmp_path / "corrupted_header.chd"

        header = bytearray(124)
        header[0:8] = b"MComprHD"
        # Corrupt the version field with invalid bytes
        header[12:16] = b"\xff\xff\xff\xff"  # This will be read as 4294967295

        chd_file.write_bytes(header)

        result = extract_chd_hash(chd_file)

        # Should return None because version is not 5
        assert result is None

    def test_extract_chd_hash_zero_sha1(self, tmp_path):
        """Test handling of all-zero SHA1 hash (edge case but valid)"""
        chd_file = tmp_path / "zero_hash.chd"

        header = bytearray(124)
        header[0:8] = b"MComprHD"
        header[12:16] = int(5).to_bytes(4, "big")
        # All-zero hash
        header[84:104] = b"\x00" * 20

        chd_file.write_bytes(header)

        result = extract_chd_hash(chd_file)

        assert result
        assert result == "0" * 40
        assert len(result) == 40

    def test_extract_chd_hash_max_sha1(self, tmp_path):
        """Test handling of maximum SHA1 hash (all 0xFF - edge case but valid)"""
        chd_file = tmp_path / "max_hash.chd"

        header = bytearray(124)
        header[0:8] = b"MComprHD"
        header[12:16] = int(5).to_bytes(4, "big")
        # All-FF hash
        header[84:104] = b"\xff" * 20

        chd_file.write_bytes(header)

        result = extract_chd_hash(chd_file)

        assert result
        assert result == "f" * 40
        assert len(result) == 40
