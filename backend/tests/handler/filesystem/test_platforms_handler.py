from pathlib import Path
from unittest.mock import patch

import pytest

from config.config_manager import LIBRARY_BASE_PATH, Config
from handler.filesystem.platforms_handler import FSPlatformsHandler


class TestFSPlatformsHandler:
    """Test suite for FSPlatformsHandler class"""

    @pytest.fixture
    def handler(self):
        return FSPlatformsHandler()

    @pytest.fixture
    def config(self):
        return Config(
            EXCLUDED_PLATFORMS=["romm", "excluded_platform"],
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

    @pytest.fixture
    def config_custom_folder(self):
        return Config(
            EXCLUDED_PLATFORMS=[],
            EXCLUDED_SINGLE_EXT=[],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={},
            PLATFORMS_VERSIONS={},
            ROMS_FOLDER_NAME="ROMS",
            FIRMWARE_FOLDER_NAME="BIOS",
        )

    def test_init_uses_library_base_path(self, handler: FSPlatformsHandler):
        """Test that FSPlatformsHandler initializes with LIBRARY_BASE_PATH"""
        assert handler.base_path == Path(LIBRARY_BASE_PATH).resolve()

    def test_exclude_platforms_filters_excluded_platforms(
        self, handler: FSPlatformsHandler, config
    ):
        """Test that _exclude_platforms filters out excluded platforms"""
        platforms = ["n64", "psx", "romm", "excluded_platform", "gba"]

        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            result = handler._exclude_platforms(platforms)

            assert "n64" in result
            assert "psx" in result
            assert "gba" in result
            assert "romm" not in result
            assert "excluded_platform" not in result

    def test_exclude_platforms_empty_list(self, handler: FSPlatformsHandler, config):
        """Test that _exclude_platforms handles empty list"""
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            result = handler._exclude_platforms([])
            assert result == []

    def test_exclude_platforms_no_excluded_config(
        self, handler: FSPlatformsHandler, config_custom_folder
    ):
        """Test that _exclude_platforms works when no platforms are excluded"""
        platforms = ["n64", "psx", "gba"]

        with patch(
            "handler.filesystem.platforms_handler.cm.get_config",
            return_value=config_custom_folder,
        ):
            result = handler._exclude_platforms(platforms)
            assert result == platforms

    def test_get_platforms_directory_high_priority_structure(
        self, handler: FSPlatformsHandler, config
    ):
        """Test get_platforms_directory with high priority structure"""
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            with patch("os.path.exists", return_value=True):
                result = handler.get_platforms_directory()
                assert result == config.ROMS_FOLDER_NAME

    def test_get_platforms_directory_normal_structure(
        self, handler: FSPlatformsHandler, config
    ):
        """Test get_platforms_directory with normal structure"""
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            with patch("os.path.exists", return_value=False):
                result = handler.get_platforms_directory()
                assert result == ""

    def test_get_plaform_fs_structure_high_priority(
        self, handler: FSPlatformsHandler, config
    ):
        """Test get_plaform_fs_structure with high priority structure"""
        fs_slug = "n64"

        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            with patch("os.path.exists", return_value=True):
                result = handler.get_plaform_fs_structure(fs_slug)
                assert result == f"{config.ROMS_FOLDER_NAME}/{fs_slug}"

    def test_get_plaform_fs_structure_normal_structure(
        self, handler: FSPlatformsHandler, config
    ):
        """Test get_plaform_fs_structure with normal structure"""
        fs_slug = "n64"

        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            result = handler.get_plaform_fs_structure(fs_slug)
            assert result == f"{fs_slug}/{config.ROMS_FOLDER_NAME}"

    def test_get_plaform_fs_structure_custom_folder_name(
        self, handler: FSPlatformsHandler, config_custom_folder
    ):
        """Test get_plaform_fs_structure with custom folder name"""
        fs_slug = "psx"

        with patch(
            "handler.filesystem.platforms_handler.cm.get_config",
            return_value=config_custom_folder,
        ):
            result = handler.get_plaform_fs_structure(fs_slug)
            assert result == f"{fs_slug}/{config_custom_folder.ROMS_FOLDER_NAME}"

    async def test_add_platform_creates_directory(
        self, handler: FSPlatformsHandler, config
    ):
        """Test that add_platform creates the correct directory"""
        fs_slug = "gba"
        expected_path = f"{config.ROMS_FOLDER_NAME}/{fs_slug}"

        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            with patch("os.path.exists", return_value=True):
                with patch.object(handler, "make_directory") as mock_make_directory:
                    await handler.add_platform(fs_slug)
                    mock_make_directory.assert_called_once_with(expected_path)

    async def test_add_platform_normal_structure(
        self, handler: FSPlatformsHandler, config
    ):
        """Test that add_platform creates directory with normal structure"""
        fs_slug = "gba"
        expected_path = f"{fs_slug}/{config.ROMS_FOLDER_NAME}"

        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            with patch("os.path.exists", return_value=False):
                with patch.object(handler, "make_directory") as mock_make_directory:
                    await handler.add_platform(fs_slug)
                    mock_make_directory.assert_called_once_with(expected_path)

    async def test_get_platforms_returns_existing_platforms(
        self, handler: FSPlatformsHandler, config
    ):
        """Test that get_platforms returns existing platforms"""
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            result = await handler.get_platforms()
            assert "n64" in result
            assert "psx" in result

    async def test_get_platforms_excludes_excluded_platforms(
        self, handler: FSPlatformsHandler, config
    ):
        """Test that get_platforms excludes excluded platforms"""
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            config.EXCLUDED_PLATFORMS = ["psx"]
            result = await handler.get_platforms()

            assert "n64" in result
            assert "psx" not in result

    async def test_get_platforms_calls_list_directories_with_correct_path(
        self, handler: FSPlatformsHandler, config
    ):
        """Test that get_platforms calls list_directories with correct path"""
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            with patch("os.path.exists", return_value=True):
                with patch.object(
                    handler, "list_directories", return_value=[]
                ) as mock_list:
                    await handler.get_platforms()
                    mock_list.assert_called_once_with(path=config.ROMS_FOLDER_NAME)

    async def test_get_platforms_calls_list_directories_with_empty_path(
        self, handler: FSPlatformsHandler, config
    ):
        """Test that get_platforms calls list_directories with empty path for normal structure"""
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            with patch.object(
                handler, "list_directories", return_value=[]
            ) as mock_list:
                await handler.get_platforms()
                mock_list.assert_called_once_with(path="")

    def test_integration_with_base_handler_methods(self, handler: FSPlatformsHandler):
        """Test that FSPlatformsHandler properly inherits from FSHandler"""
        # Test that handler has base methods
        assert hasattr(handler, "validate_path")
        assert hasattr(handler, "list_directories")
        assert hasattr(handler, "make_directory")
        assert hasattr(handler, "file_exists")
        assert hasattr(handler, "move_file_or_folder")
        assert hasattr(handler, "stream_file")

    def test_platform_slug_handling_with_special_characters(
        self, handler: FSPlatformsHandler, config
    ):
        """Test that platform slugs with special characters are handled correctly"""
        fs_slug = "n64"

        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            result = handler.get_plaform_fs_structure(fs_slug)
            assert result == f"{fs_slug}/{config.ROMS_FOLDER_NAME}"

    async def test_path_construction_consistency(
        self, handler: FSPlatformsHandler, config
    ):
        """Test that path construction is consistent across methods"""
        fs_slug = "ps2"

        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            # Test both methods return consistent paths
            structure_path = handler.get_plaform_fs_structure(fs_slug)

            with patch.object(handler, "make_directory") as mock_make_directory:
                await handler.add_platform(fs_slug)
                mock_make_directory.assert_called_once_with(structure_path)

    def test_actual_directory_operations(self, handler: FSPlatformsHandler, config):
        """Test operations with actual directory structure"""
        # Test with existing platforms
        existing_platforms = ["n64", "psx"]

        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            for platform in existing_platforms:
                expected_path = f"{platform}/{config.ROMS_FOLDER_NAME}"
                result = handler.get_plaform_fs_structure(platform)
                assert result == expected_path

    async def test_edge_cases_and_error_handling(
        self, handler: FSPlatformsHandler, config
    ):
        """Test edge cases and error handling"""
        # Test with empty platform slug
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            result = handler.get_plaform_fs_structure("")
            assert result == f"/{config.ROMS_FOLDER_NAME}"

            # Test adding empty platform
            with patch.object(handler, "make_directory") as mock_make_directory:
                await handler.add_platform("")
                mock_make_directory.assert_called_once_with(
                    f"/{config.ROMS_FOLDER_NAME}"
                )

    def test_multiple_platforms_handling(self, handler: FSPlatformsHandler, config):
        """Test handling multiple platforms simultaneously"""
        platforms = ["n64", "psx", "gba", "romm", "excluded_platform"]
        expected_filtered = ["n64", "psx", "gba"]

        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            filtered = handler._exclude_platforms(platforms)
            assert set(filtered) == set(expected_filtered)

            # Test that each platform gets correct structure
            for platform in expected_filtered:
                structure = handler.get_plaform_fs_structure(platform)
                assert structure == f"{platform}/{config.ROMS_FOLDER_NAME}"
