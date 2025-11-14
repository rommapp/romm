import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from config.config_manager import LIBRARY_BASE_PATH, Config
from handler.filesystem.roms_handler import FileHash, FSRomsHandler
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
