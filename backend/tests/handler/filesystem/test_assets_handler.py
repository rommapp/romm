import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from handler.filesystem.assets_handler import ASSETS_BASE_PATH, FSAssetsHandler
from models.user import User


class TestFSAssetsHandler:
    """Test suite for FSAssetsHandler class"""

    @pytest.fixture
    def handler(self):
        return FSAssetsHandler()

    def test_init_uses_assets_base_path(self, handler: FSAssetsHandler):
        """Test that FSAssetsHandler initializes with ASSETS_BASE_PATH"""
        assert handler.base_path == Path(ASSETS_BASE_PATH).resolve()

    def test_user_folder_path(self, handler: FSAssetsHandler, editor_user: User):
        """Test user_folder_path method"""
        result = handler.user_folder_path(editor_user)
        expected = os.path.join("users", editor_user.fs_safe_folder_name)
        assert result == expected

    def test_build_avatar_path(self, handler: FSAssetsHandler, editor_user: User):
        """Test build_avatar_path method"""
        result = handler.build_avatar_path(editor_user)
        expected = os.path.join("users", editor_user.fs_safe_folder_name, "profile")
        assert result == expected

    def test_build_saves_file_path_without_emulator(
        self, handler: FSAssetsHandler, editor_user: User
    ):
        """Test build_saves_file_path method without emulator"""
        platform_fs_slug = "n64"
        rom_id = 456

        result = handler.build_saves_file_path(
            user=editor_user, platform_fs_slug=platform_fs_slug, rom_id=rom_id
        )

        expected = os.path.join(
            "users",
            editor_user.fs_safe_folder_name,
            "saves",
            platform_fs_slug,
            str(rom_id),
        )
        assert result == expected

    def test_build_saves_file_path_with_emulator(
        self, handler: FSAssetsHandler, editor_user: User
    ):
        """Test build_saves_file_path method with emulator"""
        platform_fs_slug = "n64"
        rom_id = 456
        emulator = "mupen64plus"

        result = handler.build_saves_file_path(
            user=editor_user,
            platform_fs_slug=platform_fs_slug,
            rom_id=rom_id,
            emulator=emulator,
        )

        expected = os.path.join(
            "users",
            editor_user.fs_safe_folder_name,
            "saves",
            platform_fs_slug,
            str(rom_id),
            emulator,
        )
        assert result == expected

    def test_build_states_file_path_without_emulator(
        self, handler: FSAssetsHandler, editor_user: User
    ):
        """Test build_states_file_path method without emulator"""
        platform_fs_slug = "snes"
        rom_id = 789

        result = handler.build_states_file_path(
            user=editor_user, platform_fs_slug=platform_fs_slug, rom_id=rom_id
        )

        expected = os.path.join(
            "users",
            editor_user.fs_safe_folder_name,
            "states",
            platform_fs_slug,
            str(rom_id),
        )
        assert result == expected

    def test_build_states_file_path_with_emulator(
        self, handler: FSAssetsHandler, editor_user: User
    ):
        """Test build_states_file_path method with emulator"""
        platform_fs_slug = "snes"
        rom_id = 789
        emulator = "snes9x"

        result = handler.build_states_file_path(
            user=editor_user,
            platform_fs_slug=platform_fs_slug,
            rom_id=rom_id,
            emulator=emulator,
        )

        expected = os.path.join(
            "users",
            editor_user.fs_safe_folder_name,
            "states",
            platform_fs_slug,
            str(rom_id),
            emulator,
        )
        assert result == expected

    def test_build_screenshots_file_path(
        self, handler: FSAssetsHandler, editor_user: User
    ):
        """Test build_screenshots_file_path method"""
        platform_fs_slug = "psx"
        rom_id = 101

        result = handler.build_screenshots_file_path(
            user=editor_user, platform_fs_slug=platform_fs_slug, rom_id=rom_id
        )

        expected = os.path.join(
            "users",
            editor_user.fs_safe_folder_name,
            "screenshots",
            platform_fs_slug,
            str(rom_id),
        )
        assert result == expected

    def test_build_asset_file_path_internal_method(
        self, handler: FSAssetsHandler, editor_user: User
    ):
        """Test _build_asset_file_path internal method"""
        folder = "custom_folder"
        platform_fs_slug = "gba"
        rom_id = 999
        emulator = "mgba"

        result = handler._build_asset_file_path(
            user=editor_user,
            folder=folder,
            platform_fs_slug=platform_fs_slug,
            rom_id=rom_id,
            emulator=emulator,
        )

        expected = os.path.join(
            "users",
            editor_user.fs_safe_folder_name,
            folder,
            platform_fs_slug,
            str(rom_id),
            emulator,
        )
        assert result == expected

    def test_build_asset_file_path_without_emulator(
        self, handler: FSAssetsHandler, editor_user: User
    ):
        """Test _build_asset_file_path internal method without emulator"""
        folder = "custom_folder"
        platform_fs_slug = "gba"
        rom_id = 999

        result = handler._build_asset_file_path(
            user=editor_user,
            folder=folder,
            platform_fs_slug=platform_fs_slug,
            rom_id=rom_id,
        )

        expected = os.path.join(
            "users",
            editor_user.fs_safe_folder_name,
            folder,
            platform_fs_slug,
            str(rom_id),
        )
        assert result == expected

    def test_integration_with_real_user_fixture(
        self, handler: FSAssetsHandler, admin_user: User
    ):
        """Test integration with real user fixture from the project"""
        platform_fs_slug = "n64"
        rom_id = 123
        emulator = "mupen64plus"

        # Test saves path
        saves_path = handler.build_saves_file_path(
            user=admin_user,
            platform_fs_slug=platform_fs_slug,
            rom_id=rom_id,
            emulator=emulator,
        )

        assert saves_path.startswith("users/")
        assert platform_fs_slug in saves_path
        assert str(rom_id) in saves_path
        assert emulator in saves_path

        # Test states path
        states_path = handler.build_states_file_path(
            user=admin_user,
            platform_fs_slug=platform_fs_slug,
            rom_id=rom_id,
            emulator=emulator,
        )

        assert states_path.startswith("users/")
        assert platform_fs_slug in states_path
        assert str(rom_id) in states_path
        assert emulator in states_path

        # Test screenshots path
        screenshots_path = handler.build_screenshots_file_path(
            user=admin_user, platform_fs_slug=platform_fs_slug, rom_id=rom_id
        )

        assert screenshots_path.startswith("users/")
        assert platform_fs_slug in screenshots_path
        assert str(rom_id) in screenshots_path

        # Test avatar path
        avatar_path = handler.build_avatar_path(admin_user)
        assert avatar_path.startswith("users/")
        assert "profile" in avatar_path

    def test_paths_are_relative_to_base_path(
        self, handler: FSAssetsHandler, editor_user: User
    ):
        """Test that all generated paths are relative to the base path"""
        platform_fs_slug = "ps1"
        rom_id = 555
        emulator = "duckstation"

        # Test various path methods
        paths = [
            handler.user_folder_path(editor_user),
            handler.build_avatar_path(editor_user),
            handler.build_saves_file_path(editor_user, platform_fs_slug, rom_id),
            handler.build_saves_file_path(
                editor_user, platform_fs_slug, rom_id, emulator
            ),
            handler.build_states_file_path(editor_user, platform_fs_slug, rom_id),
            handler.build_states_file_path(
                editor_user, platform_fs_slug, rom_id, emulator
            ),
            handler.build_screenshots_file_path(editor_user, platform_fs_slug, rom_id),
        ]

        for path in paths:
            # Ensure paths are relative (don't start with /)
            assert not os.path.isabs(path), f"Path should be relative: {path}"

            # Ensure paths can be resolved within the base path
            full_path = handler.validate_path(path)
            assert full_path.is_relative_to(handler.base_path)

    def test_different_users_have_different_paths(self, handler: FSAssetsHandler):
        """Test that different users get different folder paths"""
        user1 = Mock(spec=User)
        user1.id = 1
        user1.fs_safe_folder_name = "User:1".encode().hex()

        user2 = Mock(spec=User)
        user2.id = 2
        user2.fs_safe_folder_name = "User:2".encode().hex()

        path1 = handler.user_folder_path(user1)
        path2 = handler.user_folder_path(user2)

        assert path1 != path2
        assert user1.fs_safe_folder_name in path1
        assert user2.fs_safe_folder_name in path2

    def test_rom_id_conversion_to_string(
        self, handler: FSAssetsHandler, editor_user: User
    ):
        """Test that rom_id is properly converted to string in paths"""
        platform_fs_slug = "dc"
        rom_id = 12345

        saves_path = handler.build_saves_file_path(
            user=editor_user, platform_fs_slug=platform_fs_slug, rom_id=rom_id
        )

        assert str(rom_id) in saves_path
        assert saves_path.endswith(str(rom_id))

    def test_emulator_parameter_handling(
        self, handler: FSAssetsHandler, editor_user: User
    ):
        """Test that emulator parameter is handled consistently"""
        platform_fs_slug = "ps2"
        rom_id = 777
        emulator = "pcsx2"

        # Test with emulator
        saves_with_emulator = handler.build_saves_file_path(
            user=editor_user,
            platform_fs_slug=platform_fs_slug,
            rom_id=rom_id,
            emulator=emulator,
        )

        # Test without emulator
        saves_without_emulator = handler.build_saves_file_path(
            user=editor_user, platform_fs_slug=platform_fs_slug, rom_id=rom_id
        )

        assert emulator in saves_with_emulator
        assert emulator not in saves_without_emulator
        assert saves_with_emulator.startswith(saves_without_emulator)
