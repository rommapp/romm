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
            STRUCTURE_TEMPLATES={},
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
            STRUCTURE_TEMPLATES={"default": "ROMS/{platform}/{game}"},
        )

    @pytest.fixture
    def config_platform_first(self):
        """A `{platform}/roms` layout, which is now opt-in via a template."""
        return Config(
            EXCLUDED_PLATFORMS=[],
            EXCLUDED_SINGLE_EXT=[],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={},
            PLATFORMS_VERSIONS={},
            STRUCTURE_TEMPLATES={"default": "{platform}/roms/{game}"},
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

    def test_exclude_platforms_supports_glob_patterns(
        self, handler: FSPlatformsHandler, config
    ):
        """Glob patterns in the exclusion list (e.g. .Trash-*) match directories"""
        platforms = ["n64", ".Trash-1000", "#recycle", "psx"]
        config.EXCLUDED_PLATFORMS = [".Trash-*", "#recycle"]

        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            result = handler._exclude_platforms(platforms)

            assert result == ["n64", "psx"]

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

    def test_get_platforms_directory_from_default_template(
        self, handler: FSPlatformsHandler, config
    ):
        """Platforms are enumerated in the folder above `{platform}`"""
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            assert handler.get_platforms_directory() == "roms"

    def test_get_platforms_directory_is_the_library_root_when_platform_leads(
        self, handler: FSPlatformsHandler, config_platform_first
    ):
        """A `{platform}/roms` template puts the platform folders at the root"""
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config",
            return_value=config_platform_first,
        ):
            assert handler.get_platforms_directory() == ""

    def test_get_platform_fs_structure_from_default_template(
        self, handler: FSPlatformsHandler, config
    ):
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            assert handler.get_platform_fs_structure("n64") == "roms/n64"

    def test_get_platform_fs_structure_when_platform_leads(
        self, handler: FSPlatformsHandler, config_platform_first
    ):
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config",
            return_value=config_platform_first,
        ):
            assert handler.get_platform_fs_structure("n64") == "n64/roms"

    def test_get_platform_fs_structure_custom_folder_name(
        self, handler: FSPlatformsHandler, config_custom_folder
    ):
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config",
            return_value=config_custom_folder,
        ):
            assert handler.get_platform_fs_structure("psx") == "ROMS/psx"

    async def test_add_platform_creates_directory(
        self, handler: FSPlatformsHandler, config
    ):
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            with patch.object(handler, "make_directory") as mock_make_directory:
                await handler.add_platform("gba")
                mock_make_directory.assert_called_once_with("roms/gba")

    async def test_add_platform_follows_the_configured_template(
        self, handler: FSPlatformsHandler, config_platform_first
    ):
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config",
            return_value=config_platform_first,
        ):
            with patch.object(handler, "make_directory") as mock_make_directory:
                await handler.add_platform("gba")
                mock_make_directory.assert_called_once_with("gba/roms")

    async def test_get_platforms_returns_existing_platforms(
        self, handler: FSPlatformsHandler, config_platform_first
    ):
        """Test that get_platforms returns existing platforms"""
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config",
            return_value=config_platform_first,
        ):
            result = await handler.get_platforms()
            assert "n64" in result
            assert "psx" in result

    async def test_get_platforms_excludes_excluded_platforms(
        self, handler: FSPlatformsHandler, config_platform_first
    ):
        """Test that get_platforms excludes excluded platforms"""
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config",
            return_value=config_platform_first,
        ):
            config_platform_first.EXCLUDED_PLATFORMS = ["psx"]
            result = await handler.get_platforms()

            assert "n64" in result
            assert "psx" not in result

    async def test_get_platforms_calls_list_directories_with_correct_path(
        self, handler: FSPlatformsHandler, config
    ):
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            with patch.object(
                handler, "list_directories", return_value=[]
            ) as mock_list:
                await handler.get_platforms()
                mock_list.assert_called_once_with(path="roms")

    async def test_get_platforms_calls_list_directories_with_empty_path(
        self, handler: FSPlatformsHandler, config_platform_first
    ):
        """A `{platform}/roms` template enumerates platforms at the library root"""
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config",
            return_value=config_platform_first,
        ):
            with patch.object(
                handler, "list_directories", return_value=[]
            ) as mock_list:
                await handler.get_platforms()
                mock_list.assert_called_once_with(path="")

    async def test_get_platforms_bootstraps_the_platforms_folder(
        self, handler: FSPlatformsHandler, config
    ):
        """When the platforms folder is missing, get_platforms creates it and
        returns an empty list instead of raising."""
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            with patch.object(
                handler, "list_directories", side_effect=FileNotFoundError
            ):
                with patch.object(handler, "create_library_structure") as mock_create:
                    result = await handler.get_platforms()

                    assert result == []
                    mock_create.assert_called_once()

    async def test_get_platforms_returns_empty_when_bootstrap_fails(
        self, handler: FSPlatformsHandler, config
    ):
        """If creating the default structure fails, get_platforms still returns an
        empty list rather than propagating the error (so the heartbeat stays healthy).
        """
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            with patch.object(
                handler, "list_directories", side_effect=FileNotFoundError
            ):
                with patch.object(
                    handler,
                    "create_library_structure",
                    side_effect=PermissionError("read-only filesystem"),
                ):
                    result = await handler.get_platforms()

                    assert result == []

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
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            assert handler.get_platform_fs_structure("n64") == "roms/n64"

    async def test_path_construction_consistency(
        self, handler: FSPlatformsHandler, config
    ):
        """Test that path construction is consistent across methods"""
        fs_slug = "ps2"

        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            # Test both methods return consistent paths
            structure_path = handler.get_platform_fs_structure(fs_slug)

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
                result = handler.get_platform_fs_structure(platform)
                assert result == f"roms/{platform}"

    async def test_edge_cases_and_error_handling(
        self, handler: FSPlatformsHandler, config
    ):
        """Test edge cases and error handling"""
        # Test with empty platform slug
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            assert handler.get_platform_fs_structure("") == "roms/"

            # Test adding empty platform
            with patch.object(handler, "make_directory") as mock_make_directory:
                await handler.add_platform("")
                mock_make_directory.assert_called_once_with("roms/")

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
                structure = handler.get_platform_fs_structure(platform)
                assert structure == f"roms/{platform}"

    def test_library_structure_exists_when_the_platforms_folder_is_present(
        self, handler: FSPlatformsHandler, config
    ):
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            with patch("handler.filesystem.platforms_handler.os.path.isdir") as isdir:
                isdir.return_value = True
                assert handler.library_structure_exists() is True
                assert isdir.call_args[0][0].endswith("/roms")

    def test_library_structure_exists_is_false_for_an_empty_library(
        self, handler: FSPlatformsHandler, config
    ):
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config", return_value=config
        ):
            with patch(
                "handler.filesystem.platforms_handler.os.path.isdir",
                return_value=False,
            ):
                assert handler.library_structure_exists() is False

    def test_library_structure_follows_the_configured_template(
        self, handler: FSPlatformsHandler, config_custom_folder
    ):
        """The folder checked and created is the one the template names."""
        with patch(
            "handler.filesystem.platforms_handler.cm.get_config",
            return_value=config_custom_folder,
        ):
            with patch("handler.filesystem.platforms_handler.os.makedirs") as makedirs:
                handler.create_library_structure()
                assert makedirs.call_args[0][0].endswith("/ROMS")
