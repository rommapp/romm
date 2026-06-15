import hashlib
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import Mock

import pytest
from tests._zipfile_shim import reload_zipfile

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


class TestComputeContentHash:
    """Regression coverage for compute_content_hash dispatch."""

    @pytest.fixture
    def temp_base(self):
        path = tempfile.mkdtemp()
        yield path
        shutil.rmtree(path, ignore_errors=True)

    @pytest.fixture
    def handler(self, temp_base: str):
        handler = FSAssetsHandler()
        handler.base_path = Path(temp_base).resolve()
        return handler

    @staticmethod
    def _expected_zip_hash(zip_path: Path) -> str:
        with zipfile.ZipFile(zip_path, "r") as zf:
            file_hashes = [
                f"{n}:{hashlib.md5(zf.read(n), usedforsecurity=False).hexdigest()}"
                for n in sorted(zf.namelist())
                if not n.endswith("/")
            ]
        combined = "\n".join(file_hashes)
        return hashlib.md5(combined.encode(), usedforsecurity=False).hexdigest()

    @staticmethod
    def _raw_md5(path: Path) -> str:
        h = hashlib.md5(usedforsecurity=False)
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    @pytest.mark.asyncio
    async def test_zip_dispatches_to_per_entry_hash(
        self, handler: FSAssetsHandler, temp_base: str
    ):
        """A zip file's content_hash must equal the per-entry zip-hash, not raw MD5.

        Regression for the path-resolution bug where compute_content_hash called
        zipfile.is_zipfile() with a bare relative path. Because the server WORKDIR
        is not ASSETS_BASE_PATH, that open() failed silently, is_zipfile returned
        False, and the dispatch fell through to _compute_file_hash (raw MD5) for
        every zip save.
        """
        relative = "users/test/saves/test.zip"
        zip_full = Path(temp_base) / relative
        zip_full.parent.mkdir(parents=True, exist_ok=True)
        reload_zipfile()
        with zipfile.ZipFile(zip_full, "w") as zf:
            zf.writestr("inner/a.txt", b"alpha bytes")
            zf.writestr("inner/b.bin", b"\x00\x01\x02\x03")

        expected_zip_hash = self._expected_zip_hash(zip_full)
        raw_md5 = self._raw_md5(zip_full)
        assert expected_zip_hash != raw_md5  # different algorithms; sanity check

        result = await handler.compute_content_hash(relative)

        assert result == expected_zip_hash, (
            "compute_content_hash should dispatch to per-entry zip-hash for zip "
            "files; got raw MD5 or None, meaning is_zipfile failed to resolve the "
            "relative path."
        )

    @pytest.mark.asyncio
    async def test_non_zip_returns_raw_md5(
        self, handler: FSAssetsHandler, temp_base: str
    ):
        """Non-zip files dispatch to _compute_file_hash (raw MD5)."""
        relative = "users/test/saves/test.srm"
        full = Path(temp_base) / relative
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(b"raw save data \x00\x01\xff")

        expected = self._raw_md5(full)

        result = await handler.compute_content_hash(relative)

        assert result == expected

    @pytest.mark.asyncio
    async def test_missing_file_returns_none(self, handler: FSAssetsHandler):
        result = await handler.compute_content_hash("users/missing/file.zip")
        assert result is None

    @pytest.mark.asyncio
    async def test_zip_hash_pinned_single_entry(
        self, handler: FSAssetsHandler, temp_base: str
    ):
        """Smallest possible zip: one file, stored compression. Pins the
        algorithm against a known digest. Any change to the protocol (sort,
        separator, hash, encoding) fails here.
        """
        relative = "users/test/saves/simple.zip"
        full = Path(temp_base) / relative
        full.parent.mkdir(parents=True, exist_ok=True)
        reload_zipfile()
        with zipfile.ZipFile(full, "w", zipfile.ZIP_STORED) as zf:
            zf.writestr("save.bin", b"\x42" * 256)

        # md5("save.bin:" + md5(b"\x42"*256).hexdigest())
        pinned = "b3636b49ca5c3d807adee33e75d410ca"

        result = await handler.compute_content_hash(relative)
        assert (
            result == pinned
        ), f"single-entry per-entry zip-hash drifted: got={result} want={pinned}"

    @pytest.mark.asyncio
    async def test_zip_hash_pinned_mixed(
        self, handler: FSAssetsHandler, temp_base: str
    ):
        """Three-entry zip with one subdir; baseline mixed shape."""
        relative = "users/test/saves/pinned.zip"
        full = Path(temp_base) / relative
        full.parent.mkdir(parents=True, exist_ok=True)
        reload_zipfile()
        with zipfile.ZipFile(full, "w", zipfile.ZIP_STORED) as zf:
            zf.writestr("inner/a.txt", b"alpha")
            zf.writestr("inner/b.txt", b"beta")
            zf.writestr("top.bin", b"\x00\x01\x02")

        pinned = "8cf6bb36a82a5ee4d7d15fc98599908d"

        result = await handler.compute_content_hash(relative)
        assert result == pinned, (
            f"per-entry zip-hash drifted from documented protocol: "
            f"got={result} want={pinned}"
        )

    @pytest.mark.asyncio
    async def test_zip_hash_pinned_nested_switch_shape(
        self, handler: FSAssetsHandler, temp_base: str
    ):
        """Switch-save-shaped zip: deep nesting, mixed sizes, empty file,
        unicode filename. Mirrors what real Switch saves look like (the
        original bug surface) so this test exercises the algorithm against
        a realistic layout.
        """
        relative = "users/test/saves/switch.zip"
        full = Path(temp_base) / relative
        full.parent.mkdir(parents=True, exist_ok=True)
        reload_zipfile()
        with zipfile.ZipFile(full, "w", zipfile.ZIP_STORED) as zf:
            title = "0100F2C0115B6000"
            zf.writestr(f"{title}/NX6400000-SYSTEM/SYDAT.BIN", b"system data v1")
            zf.writestr(
                f"{title}/album/000_Photo.jpg",
                b"\xff\xd8\xff\xe0jpegdata" * 8,
            )
            zf.writestr(f"{title}/album/000_Thumb.jpg", b"\xff\xd8thumbdata")
            zf.writestr(f"{title}/slot_01/caption.sav", b"slot1 caption")
            zf.writestr(f"{title}/slot_01/progress.sav", b"\x01" * 64)
            zf.writestr(f"{title}/slot_02/caption.sav", b"slot2 caption")
            zf.writestr(f"{title}/slot_02/progress.sav", b"\x02" * 64)
            zf.writestr(f"{title}/storage/CacheStorageKey.dat", b"key=abcd1234")
            zf.writestr(f"{title}/storage/empty.dat", b"")
            zf.writestr(f"{title}/Pokémon.dat", b"unicode-name")

        pinned = "c0c992d1f1f883f56065bb13b68dfdee"

        result = await handler.compute_content_hash(relative)
        assert (
            result == pinned
        ), f"nested-switch-shape zip-hash drifted: got={result} want={pinned}"
