import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from handler.database import db_device_handler, db_save_handler
from handler.filesystem.sync_handler import FSSyncHandler
from models.assets import Save
from models.device import Device, SyncMode
from models.platform import Platform
from models.rom import Rom
from models.user import User


class TestExtractDeviceAndPlatform:
    @pytest.fixture
    def temp_dir(self):
        d = tempfile.mkdtemp()
        yield d
        shutil.rmtree(d, ignore_errors=True)

    @pytest.fixture
    def handler(self):
        return FSSyncHandler.__new__(FSSyncHandler)

    @pytest.fixture(autouse=True)
    def patch_base_path(self, handler: FSSyncHandler, temp_dir):
        handler.base_path = Path(temp_dir)
        with patch("sync_watcher.get_fs_sync_handler", return_value=handler):
            yield

    def test_extract_valid_incoming_path(self, temp_dir):
        from sync_watcher import _extract_device_and_platform

        path = os.path.join(temp_dir, "device-1", "incoming", "gba", "save.sav")
        result = _extract_device_and_platform(path)
        assert result == ("device-1", "gba", "save.sav")

    def test_extract_non_incoming_path_returns_none(self, temp_dir):
        from sync_watcher import _extract_device_and_platform

        path = os.path.join(temp_dir, "device-1", "outgoing", "gba", "save.sav")
        result = _extract_device_and_platform(path)
        assert result is None

    def test_extract_too_few_parts_returns_none(self, temp_dir):
        from sync_watcher import _extract_device_and_platform

        path = os.path.join(temp_dir, "device-1", "incoming")
        result = _extract_device_and_platform(path)
        assert result is None

    def test_extract_deeply_nested_returns_leaf_filename(self, temp_dir):
        from sync_watcher import _extract_device_and_platform

        path = os.path.join(
            temp_dir, "device-1", "incoming", "gba", "subdir", "save.sav"
        )
        result = _extract_device_and_platform(path)
        assert result == ("device-1", "gba", "save.sav")

    def test_extract_path_outside_base_returns_none(self):
        from sync_watcher import _extract_device_and_platform

        result = _extract_device_and_platform("/totally/different/path")
        assert result is None


class TestEnsureConflictsDir:
    @pytest.fixture
    def temp_dir(self):
        d = tempfile.mkdtemp()
        yield d
        shutil.rmtree(d, ignore_errors=True)

    @pytest.fixture
    def handler(self):
        return FSSyncHandler.__new__(FSSyncHandler)

    @pytest.fixture(autouse=True)
    def patch_base_path(self, handler: FSSyncHandler, temp_dir):
        handler.base_path = Path(temp_dir)
        with patch("sync_watcher.get_fs_sync_handler", return_value=handler):
            yield

    def test_creates_directory_and_returns_path(self, temp_dir):
        from sync_watcher import _ensure_conflicts_dir

        result = _ensure_conflicts_dir("device-1", "gba")
        expected = os.path.join(temp_dir, "device-1", "conflicts", "gba")
        assert result == expected
        assert os.path.isdir(expected)

    def test_idempotent_no_error_on_second_call(self, temp_dir):
        from sync_watcher import _ensure_conflicts_dir

        _ensure_conflicts_dir("device-1", "gba")
        result = _ensure_conflicts_dir("device-1", "gba")
        expected = os.path.join(temp_dir, "device-1", "conflicts", "gba")
        assert result == expected
        assert os.path.isdir(expected)


class TestProcessSyncChanges:
    def test_empty_changes_returns_immediately(self):
        with patch("sync_watcher.ENABLE_SYNC_FOLDER_WATCHER", True):
            from sync_watcher import process_sync_changes

            process_sync_changes([])

    def test_disabled_watcher_returns_immediately(self):
        with patch("sync_watcher.ENABLE_SYNC_FOLDER_WATCHER", False):
            from sync_watcher import process_sync_changes

            process_sync_changes([("added", "/some/path/file.sav")])


class TestProcessIncomingFileFilenameOnlyMatching:
    """Bug R2: `_process_incoming_file` matches incoming files purely by
    filename, with no slot check. An incoming device push whose filename
    collides with a null-slot archival save will overwrite the archival row.
    """

    @pytest.fixture
    def temp_dir(self):
        d = tempfile.mkdtemp()
        yield d
        shutil.rmtree(d, ignore_errors=True)

    @pytest.fixture(autouse=True)
    def patch_fs_sync_handler(self, temp_dir):
        handler = FSSyncHandler.__new__(FSSyncHandler)
        handler.base_path = Path(temp_dir)
        with patch("sync_watcher.get_fs_sync_handler", return_value=handler):
            yield handler

    @pytest.fixture
    def device(self, admin_user: User) -> Device:
        return db_device_handler.add_device(
            Device(
                id="watcher-dev-1",
                user_id=admin_user.id,
                sync_mode=SyncMode.FILE_TRANSFER,
                sync_enabled=True,
            )
        )

    @pytest.fixture
    def incoming_file(self, temp_dir, device: Device, platform: Platform):
        """Create a real incoming file the watcher will hash and stat."""
        incoming_dir = Path(temp_dir) / device.id / "incoming" / platform.fs_slug
        incoming_dir.mkdir(parents=True, exist_ok=True)
        path = incoming_dir / "collision.sav"
        path.write_bytes(b"incoming bytes from device, must not clobber archival")
        return str(path)

    def test_archival_save_is_not_overwritten_by_filename_collision(
        self,
        device: Device,
        admin_user: User,
        rom: Rom,
        platform: Platform,
        incoming_file: str,
    ):
        """Only an archival (null-slot) save exists with the colliding name.
        A device push of a file with that name must NOT overwrite the archival
        row's bytes, hash, or size — there is no slotted save to match.
        """
        from sync_watcher import _process_incoming_file

        archival = db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="collision.sav",
                file_name_no_tags="collision",
                file_name_no_ext="collision",
                file_extension="sav",
                emulator="test_emulator",
                slot=None,
                file_path=f"{platform.slug}/saves/test_emulator",
                file_size_bytes=12345,
                content_hash="archival_pinned_hash",
            )
        )

        # Force a server-side overwrite path if the bug picks the archival.
        with patch("sync_watcher.compare_save_state") as mock_cmp, patch(
            "sync_watcher.fs_asset_handler"
        ), patch("sync_watcher.asyncio") as mock_asyncio:
            mock_cmp.return_value = MagicMock(action="upload", reason=None)
            mock_asyncio.run = MagicMock()
            _process_incoming_file(
                device=device,
                session_id=1,
                platform_slug=platform.fs_slug,
                filename="collision.sav",
                full_path=incoming_file,
            )

        # The archival row's hash/size MUST be untouched.
        refreshed = db_save_handler.get_save(user_id=admin_user.id, id=archival.id)
        assert refreshed is not None
        assert refreshed.content_hash == "archival_pinned_hash"
        assert refreshed.file_size_bytes == 12345

    def test_slotted_save_is_matched_when_archival_collides_on_filename(
        self,
        device: Device,
        admin_user: User,
        rom: Rom,
        platform: Platform,
        incoming_file: str,
    ):
        """When both an archival and a slotted save share the filename, the
        watcher must pick the slotted save (the device-uploaded shape). The
        bug picks the first row returned, which can be the archival.
        """
        from sync_watcher import _process_incoming_file

        # Insert archival FIRST so unfiltered iteration order favours it.
        archival = db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="collision.sav",
                file_name_no_tags="collision",
                file_name_no_ext="collision",
                file_extension="sav",
                emulator="test_emulator",
                slot=None,
                file_path=f"{platform.slug}/saves/test_emulator",
                file_size_bytes=12345,
                content_hash="archival_pinned_hash",
            )
        )
        slotted = db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="collision.sav",
                file_name_no_tags="collision",
                file_name_no_ext="collision",
                file_extension="sav",
                emulator="test_emulator",
                slot="autosave",
                file_path=f"{platform.slug}/saves/test_emulator",
                file_size_bytes=99,
                content_hash="slotted_old_hash",
            )
        )

        with patch("sync_watcher.compare_save_state") as mock_cmp, patch(
            "sync_watcher.fs_asset_handler"
        ), patch("sync_watcher.asyncio") as mock_asyncio:
            mock_cmp.return_value = MagicMock(action="upload", reason=None)
            mock_asyncio.run = MagicMock()
            _process_incoming_file(
                device=device,
                session_id=1,
                platform_slug=platform.fs_slug,
                filename="collision.sav",
                full_path=incoming_file,
            )

        # The slotted save should be the one updated. The archival must remain.
        archival_after = db_save_handler.get_save(user_id=admin_user.id, id=archival.id)
        slotted_after = db_save_handler.get_save(user_id=admin_user.id, id=slotted.id)
        assert archival_after is not None
        assert slotted_after is not None
        assert (
            archival_after.content_hash == "archival_pinned_hash"
        ), "archival row was overwritten by filename-only match"
        assert (
            slotted_after.content_hash != "slotted_old_hash"
        ), "slotted save should have been updated, but the bug picked archival"
