import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from handler.filesystem.sync_handler import FSSyncHandler


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
        with patch("sync_watcher.fs_sync_handler", handler):
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
        with patch("sync_watcher.fs_sync_handler", handler):
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
