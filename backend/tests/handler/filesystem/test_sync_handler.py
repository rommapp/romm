"""Tests for filesystem sync handler."""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from handler.filesystem.sync_handler import FSSyncHandler


class TestFSSyncHandler:
    @pytest.fixture
    def temp_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def handler(self):
        return FSSyncHandler.__new__(FSSyncHandler)

    @pytest.fixture(autouse=True)
    def patch_base_path(self, handler: FSSyncHandler, temp_dir):
        handler.base_path = Path(temp_dir)

    def test_build_incoming_path(self, handler: FSSyncHandler):
        path = handler.build_incoming_path("device-1")
        assert path == os.path.join("device-1", "incoming")

    def test_build_incoming_path_with_platform(self, handler):
        path = handler.build_incoming_path("device-1", "gba")
        assert path == os.path.join("device-1", "incoming", "gba")

    def test_build_outgoing_path(self, handler: FSSyncHandler):
        path = handler.build_outgoing_path("device-1")
        assert path == os.path.join("device-1", "outgoing")

    def test_build_outgoing_path_with_platform(self, handler: FSSyncHandler):
        path = handler.build_outgoing_path("device-1", "snes")
        assert path == os.path.join("device-1", "outgoing", "snes")

    def test_build_conflicts_path(self, handler: FSSyncHandler):
        path = handler.build_conflicts_path("device-1", "gba")
        assert path == os.path.join("device-1", "conflicts", "gba")

    def test_ensure_device_directories(self, handler: FSSyncHandler, temp_dir):
        handler.ensure_device_directories("test-device")
        incoming = handler.base_path / handler.build_incoming_path("test-device")
        outgoing = handler.base_path / handler.build_outgoing_path("test-device")
        assert os.path.isdir(incoming)
        assert os.path.isdir(outgoing)

    def test_list_incoming_files_empty(self, handler: FSSyncHandler):
        result = handler.list_incoming_files("nonexistent-device")
        assert result == []

    def test_list_incoming_files(self, handler: FSSyncHandler, temp_dir):
        handler.ensure_device_directories("dev-1")
        incoming_path = str(
            handler.base_path / handler.build_incoming_path("dev-1", "gba")
        )
        os.makedirs(incoming_path, exist_ok=True)
        test_file = os.path.join(incoming_path, "save.sav")
        with open(test_file, "wb") as f:
            f.write(b"test save content")

        result = handler.list_incoming_files("dev-1")
        assert len(result) == 1
        assert result[0]["platform_slug"] == "gba"
        assert result[0]["file_name"] == "save.sav"
        assert result[0]["file_size"] == 17

    def test_compute_file_hash(self, handler: FSSyncHandler, temp_dir):
        test_file = os.path.join(temp_dir, "test.bin")
        with open(test_file, "wb") as f:
            f.write(b"hello world")

        hash1 = handler.compute_file_hash(test_file)
        hash2 = handler.compute_file_hash(test_file)
        assert hash1 == hash2
        assert len(hash1) == 32  # MD5 hex length

    def test_compute_file_hash_different_content(
        self, handler: FSSyncHandler, temp_dir
    ):
        file_a = os.path.join(temp_dir, "a.bin")
        file_b = os.path.join(temp_dir, "b.bin")
        with open(file_a, "wb") as f:
            f.write(b"content a")
        with open(file_b, "wb") as f:
            f.write(b"content b")

        assert handler.compute_file_hash(file_a) != handler.compute_file_hash(file_b)

    def test_write_outgoing_file(self, handler: FSSyncHandler, temp_dir):
        path = handler.write_outgoing_file(
            device_id="dev-1",
            platform_slug="gba",
            file_name="save.sav",
            data=b"outgoing save data",
        )
        assert os.path.isfile(path)
        with open(path, "rb") as f:
            assert f.read() == b"outgoing save data"

    def test_remove_incoming_file(self, handler: FSSyncHandler, temp_dir):
        handler.ensure_device_directories("dev-1")
        incoming = str(handler.base_path / handler.build_incoming_path("dev-1", "gba"))
        os.makedirs(incoming, exist_ok=True)
        test_file = os.path.join(incoming, "to_remove.sav")
        with open(test_file, "wb") as f:
            f.write(b"data")

        assert os.path.exists(test_file)
        handler.remove_incoming_file(test_file)
        assert not os.path.exists(test_file)

    def test_remove_incoming_file_outside_base_raises(
        self, handler: FSSyncHandler, temp_dir
    ):
        outside_file = os.path.join(tempfile.gettempdir(), "outside.txt")
        with open(outside_file, "w") as f:
            f.write("should not be deleted")

        with pytest.raises(ValueError, match="outside the sync base directory"):
            handler.remove_incoming_file(outside_file)

        # Cleanup
        os.unlink(outside_file)

    def test_remove_incoming_file_nonexistent(self, handler: FSSyncHandler):
        # Should not raise for nonexistent files
        handler.remove_incoming_file("/nonexistent/path/file.sav")
