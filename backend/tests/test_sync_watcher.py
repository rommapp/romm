import hashlib
import os
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from tests._zipfile_shim import reload_zipfile
from tests.factories import make_save

from handler.database import (
    db_deleted_asset_handler,
    db_device_handler,
    db_device_save_sync_handler,
    db_save_handler,
    db_sync_session_handler,
)
from handler.filesystem.assets_handler import hash_save_file
from handler.filesystem.sync_handler import FSSyncHandler
from models.assets import Save
from models.device import Device, SyncMode
from models.platform import Platform
from models.rom import Rom
from models.sync_session import SyncSessionStatus
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

        archival = make_save(
            rom,
            admin_user,
            "collision.sav",
            emulator="test_emulator",
            slot=None,
            file_path=f"{platform.slug}/saves/test_emulator",
            file_size_bytes=12345,
            content_hash="archival_pinned_hash",
        )

        # Force a server-side overwrite path if the bug picks the archival.
        with (
            patch("sync_watcher.compare_save_state") as mock_cmp,
            patch("sync_watcher.fs_asset_handler"),
            patch("sync_watcher.asyncio") as mock_asyncio,
        ):
            mock_cmp.return_value = MagicMock(action="upload", reason=None)
            mock_asyncio.run = MagicMock(
                side_effect=lambda awaitable: awaitable.close()
            )
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
        archival = make_save(
            rom,
            admin_user,
            "collision.sav",
            emulator="test_emulator",
            slot=None,
            file_path=f"{platform.slug}/saves/test_emulator",
            file_size_bytes=12345,
            content_hash="archival_pinned_hash",
        )
        slotted = make_save(
            rom,
            admin_user,
            "collision.sav",
            emulator="test_emulator",
            slot="autosave",
            file_path=f"{platform.slug}/saves/test_emulator",
            file_size_bytes=99,
            content_hash="slotted_old_hash",
        )

        with (
            patch("sync_watcher.compare_save_state") as mock_cmp,
            patch("sync_watcher.fs_asset_handler"),
            patch("sync_watcher.asyncio") as mock_asyncio,
        ):
            mock_cmp.return_value = MagicMock(action="upload", reason=None)
            mock_asyncio.run = MagicMock(
                side_effect=lambda awaitable: awaitable.close()
            )
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

    def test_the_matched_slots_removals_reach_the_comparison(
        self,
        device: Device,
        admin_user: User,
        rom: Rom,
        platform: Platform,
        incoming_file: str,
    ):
        from sync_watcher import _process_incoming_file

        make_save(
            rom,
            admin_user,
            "collision.sav",
            emulator="test_emulator",
            slot="autosave",
            file_path=f"{platform.slug}/saves/test_emulator",
            file_size_bytes=99,
            content_hash="current",
        )
        db_deleted_asset_handler.record_deletion(
            admin_user.id, rom.id, "autosave", "removed_here"
        )

        with patch("sync_watcher.compare_save_state") as mock_cmp:
            mock_cmp.return_value = MagicMock(action="no_op", reason=None)
            _process_incoming_file(
                device=device,
                session_id=1,
                platform_slug=platform.fs_slug,
                filename="collision.sav",
                full_path=incoming_file,
            )

        assert set(mock_cmp.call_args.kwargs["removed_at"]) == {"removed_here"}


class TestProcessIncomingFileBaseline:
    """The watcher must record the boundary it proves and consult it next time."""

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
                id="watcher-baseline-dev",
                user_id=admin_user.id,
                sync_mode=SyncMode.FILE_TRANSFER,
                sync_enabled=True,
            )
        )

    @pytest.fixture
    def incoming_bytes(self) -> bytes:
        return b"device save bytes, unchanged since the last sync"

    @pytest.fixture
    def incoming_file(
        self, temp_dir, device: Device, platform: Platform, incoming_bytes
    ):
        incoming_dir = Path(temp_dir) / device.id / "incoming" / platform.fs_slug
        incoming_dir.mkdir(parents=True, exist_ok=True)
        path = incoming_dir / "baseline.sav"
        path.write_bytes(incoming_bytes)
        return str(path)

    @staticmethod
    def _save(
        admin_user: User,
        rom: Rom,
        platform: Platform,
        content_hash: str,
        updated_at: datetime | None = None,
    ) -> Save:
        return make_save(
            rom,
            admin_user,
            "baseline.sav",
            emulator="test_emulator",
            slot="autosave",
            file_path=f"{platform.slug}/saves/test_emulator",
            file_size_bytes=100,
            content_hash=content_hash,
            updated_at=updated_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    def test_comparison_receives_the_recorded_baseline(
        self,
        device: Device,
        admin_user: User,
        rom: Rom,
        platform: Platform,
        incoming_file: str,
    ):
        from sync_watcher import _process_incoming_file

        save = self._save(admin_user, rom, platform, "server_old")
        db_device_save_sync_handler.upsert_sync(
            device.id,
            save.id,
            synced_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
            last_sync_hash="client_at_boundary",
            last_sync_server_hash="server_at_boundary",
        )

        with patch("sync_watcher.compare_save_state") as mock_cmp:
            mock_cmp.return_value = MagicMock(action="no_op", reason=None)
            _process_incoming_file(
                device=device,
                session_id=1,
                platform_slug=platform.fs_slug,
                filename="baseline.sav",
                full_path=incoming_file,
            )

        kwargs = mock_cmp.call_args.kwargs
        assert kwargs["device_last_sync_hash"] == "client_at_boundary"
        assert kwargs["device_last_sync_server_hash"] == "server_at_boundary"

    def test_upload_records_both_halves_from_the_device_file(
        self,
        device: Device,
        admin_user: User,
        rom: Rom,
        platform: Platform,
        incoming_file: str,
        incoming_bytes: bytes,
    ):
        from sync_watcher import _process_incoming_file

        save = self._save(admin_user, rom, platform, "server_old")

        with (
            patch("sync_watcher.compare_save_state") as mock_cmp,
            patch("sync_watcher.fs_asset_handler"),
            patch("sync_watcher.asyncio") as mock_asyncio,
        ):
            mock_cmp.return_value = MagicMock(action="upload", reason=None)
            mock_asyncio.run = MagicMock()
            _process_incoming_file(
                device=device,
                session_id=1,
                platform_slug=platform.fs_slug,
                filename="baseline.sav",
                full_path=incoming_file,
            )

        digest = hashlib.md5(incoming_bytes, usedforsecurity=False).hexdigest()
        sync = db_device_save_sync_handler.get_sync(device.id, save.id)
        assert sync is not None
        assert sync.last_sync_hash == digest
        assert sync.last_sync_server_hash == digest

    def test_download_records_only_the_server_half(
        self,
        temp_dir,
        device: Device,
        admin_user: User,
        rom: Rom,
        platform: Platform,
        incoming_file: str,
    ):
        from sync_watcher import _process_incoming_file

        save = self._save(admin_user, rom, platform, "server_new")
        server_file = Path(temp_dir) / "server_baseline.sav"
        server_file.write_bytes(b"server bytes")

        with (
            patch("sync_watcher.compare_save_state") as mock_cmp,
            patch("sync_watcher.fs_asset_handler") as mock_assets,
        ):
            mock_cmp.return_value = MagicMock(action="download", reason=None)
            mock_assets.validate_path.return_value = server_file
            _process_incoming_file(
                device=device,
                session_id=1,
                platform_slug=platform.fs_slug,
                filename="baseline.sav",
                full_path=incoming_file,
            )

        sync = db_device_save_sync_handler.get_sync(device.id, save.id)
        assert sync is not None
        assert sync.last_sync_hash is None
        assert sync.last_sync_server_hash == "server_new"

    def test_no_op_leaves_the_baseline_untouched(
        self,
        device: Device,
        admin_user: User,
        rom: Rom,
        platform: Platform,
        incoming_file: str,
    ):
        from sync_watcher import _process_incoming_file

        save = self._save(admin_user, rom, platform, "server_old")
        db_device_save_sync_handler.upsert_sync(
            device.id,
            save.id,
            synced_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
            last_sync_hash="client_at_boundary",
            last_sync_server_hash="server_at_boundary",
        )

        with patch("sync_watcher.compare_save_state") as mock_cmp:
            mock_cmp.return_value = MagicMock(action="no_op", reason=None)
            _process_incoming_file(
                device=device,
                session_id=1,
                platform_slug=platform.fs_slug,
                filename="baseline.sav",
                full_path=incoming_file,
            )

        sync = db_device_save_sync_handler.get_sync(device.id, save.id)
        assert sync is not None
        assert sync.last_sync_hash == "client_at_boundary"
        assert sync.last_sync_server_hash == "server_at_boundary"
        assert not os.path.exists(incoming_file)

    def test_an_unchanged_device_file_downloads_instead_of_conflicting(
        self,
        temp_dir,
        device: Device,
        admin_user: User,
        rom: Rom,
        platform: Platform,
        incoming_file: str,
        incoming_bytes: bytes,
    ):
        """A rewritten-but-identical device file must not be read as a change."""
        from sync_watcher import _process_incoming_file

        server_file = Path(temp_dir) / "server_baseline.sav"
        server_file.write_bytes(b"server bytes")
        save = self._save(
            admin_user,
            rom,
            platform,
            "server_new",
            updated_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
        )
        db_device_save_sync_handler.upsert_sync(
            device.id,
            save.id,
            synced_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
            last_sync_hash=hashlib.md5(
                incoming_bytes, usedforsecurity=False
            ).hexdigest(),
            last_sync_server_hash="server_old",
        )

        with (
            patch("sync_watcher.fs_asset_handler") as mock_assets,
            patch("endpoints.sockets.sync.emit_sync_conflict") as mock_emit,
        ):
            mock_assets.validate_path.return_value = server_file
            _process_incoming_file(
                device=device,
                session_id=1,
                platform_slug=platform.fs_slug,
                filename="baseline.sav",
                full_path=incoming_file,
            )

        mock_emit.assert_not_called()
        assert not os.path.exists(incoming_file)
        outgoing = (
            Path(temp_dir) / device.id / "outgoing" / platform.fs_slug / "baseline.sav"
        )
        assert outgoing.read_bytes() == b"server bytes"
        sync = db_device_save_sync_handler.get_sync(device.id, save.id)
        assert sync is not None
        assert sync.last_sync_hash is None
        assert sync.last_sync_server_hash == "server_new"

    def test_a_repacked_zip_with_the_same_entries_is_already_in_sync(
        self,
        temp_dir,
        device: Device,
        admin_user: User,
        rom: Rom,
        platform: Platform,
        incoming_file: str,
    ):
        """Device and server zips differing only in packing must match by content."""
        from sync_watcher import _process_incoming_file

        def write_zip(path: str | Path, compression: int) -> None:
            reload_zipfile()
            with zipfile.ZipFile(path, "w", compression=compression) as zf:
                zf.writestr("card/save.bin", b"identical save contents" * 64)

        write_zip(incoming_file, zipfile.ZIP_STORED)
        server_zip = Path(temp_dir) / "server.zip"
        write_zip(server_zip, zipfile.ZIP_DEFLATED)
        assert Path(incoming_file).read_bytes() != server_zip.read_bytes()
        server_hash = hash_save_file(server_zip)
        assert server_hash is not None

        save = self._save(
            admin_user,
            rom,
            platform,
            server_hash,
            updated_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
        )
        db_device_save_sync_handler.upsert_sync(
            device.id, save.id, synced_at=datetime(2026, 1, 5, tzinfo=timezone.utc)
        )

        with patch("endpoints.sockets.sync.emit_sync_conflict") as mock_emit:
            _process_incoming_file(
                device=device,
                session_id=1,
                platform_slug=platform.fs_slug,
                filename="baseline.sav",
                full_path=incoming_file,
            )

        mock_emit.assert_not_called()
        assert not os.path.exists(incoming_file)
        assert not (Path(temp_dir) / device.id / "outgoing").exists()
        sync = db_device_save_sync_handler.get_sync(device.id, save.id)
        assert sync is not None
        assert sync.last_sync_hash == save.content_hash
        assert sync.last_sync_server_hash == save.content_hash


@pytest.fixture
def sync_root(tmp_path: Path):
    handler = FSSyncHandler.__new__(FSSyncHandler)
    handler.base_path = tmp_path
    with patch("sync_watcher.get_fs_sync_handler", return_value=handler):
        yield tmp_path


def _incoming(root: Path, device_id: str, platform_slug: str, name: str) -> str:
    path = root / device_id / "incoming" / platform_slug / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"device bytes")
    return str(path)


class TestProcessSyncChangesGrouping:
    def test_groups_incoming_files_by_device(self, sync_root: Path):
        from sync_watcher import process_sync_changes

        deck_a = _incoming(sync_root, "deck", "gba", "a.srm")
        deck_b = _incoming(sync_root, "deck", "snes", "b.srm")
        handheld = _incoming(sync_root, "handheld", "gba", "c.srm")
        outgoing = sync_root / "deck" / "outgoing" / "gba" / "d.srm"
        outgoing.parent.mkdir(parents=True)
        outgoing.write_bytes(b"")

        with (
            patch("sync_watcher.ENABLE_SYNC_FOLDER_WATCHER", True),
            patch("sync_watcher._process_device_incoming") as process,
        ):
            process_sync_changes(
                [
                    ("added", deck_a),
                    ("modified", deck_b),
                    ("added", handheld),
                    ("added", str(outgoing)),
                    ("added", str(sync_root / "deck" / "incoming" / "gba")),
                    ("deleted", str(sync_root / "deck" / "incoming" / "gba" / "x")),
                ]
            )

        assert {c.args[0]: c.args[1] for c in process.call_args_list} == {
            "deck": [("gba", "a.srm", deck_a), ("snes", "b.srm", deck_b)],
            "handheld": [("gba", "c.srm", handheld)],
        }

    def test_changes_outside_any_incoming_folder_do_nothing(self, sync_root: Path):
        from sync_watcher import process_sync_changes

        stray = sync_root / "deck" / "notes.txt"
        stray.parent.mkdir(parents=True)
        stray.write_bytes(b"")

        with (
            patch("sync_watcher.ENABLE_SYNC_FOLDER_WATCHER", True),
            patch("sync_watcher._process_device_incoming") as process,
        ):
            process_sync_changes([("added", str(stray))])

        process.assert_not_called()


class TestProcessDeviceIncoming:
    FILES = [("gba", "a.srm", "/sync/deck/incoming/gba/a.srm")]

    @pytest.fixture
    def emitted(self):
        with (
            patch("endpoints.sockets.sync.emit_sync_started") as started,
            patch("endpoints.sockets.sync.emit_sync_completed") as completed,
            patch("endpoints.sockets.sync.emit_sync_error") as error,
        ):
            yield {"started": started, "completed": completed, "error": error}

    @pytest.fixture
    def process_file(self):
        with patch("sync_watcher._process_incoming_file") as process:
            yield process

    def _device(
        self,
        user: User,
        sync_mode: SyncMode = SyncMode.FILE_TRANSFER,
        sync_enabled: bool = True,
    ) -> Device:
        return db_device_handler.add_device(
            Device(
                id="watched-deck",
                user_id=user.id,
                sync_mode=sync_mode,
                sync_enabled=sync_enabled,
            )
        )

    @staticmethod
    def _sessions(device: Device):
        return db_sync_session_handler.get_sessions(
            user_id=device.user_id, device_id=device.id
        )

    def test_processes_each_file_in_one_session(
        self, admin_user: User, emitted, process_file
    ):
        from sync_watcher import _process_device_incoming

        device = self._device(admin_user)
        files = [
            ("gba", "a.srm", "/sync/watched-deck/incoming/gba/a.srm"),
            ("snes", "b.srm", "/sync/watched-deck/incoming/snes/b.srm"),
        ]

        _process_device_incoming(device.id, files)

        assert [c.args[2:] for c in process_file.call_args_list] == files
        [session] = self._sessions(device)
        assert session.status == SyncSessionStatus.COMPLETED
        assert (session.operations_planned, session.operations_completed) == (2, 2)
        emitted["started"].assert_called_once()
        emitted["completed"].assert_called_once()
        emitted["error"].assert_not_called()

    def test_a_failing_file_is_counted_and_reported(
        self, admin_user: User, emitted, process_file
    ):
        from sync_watcher import _process_device_incoming

        device = self._device(admin_user)
        process_file.side_effect = [OSError("unreadable"), None]

        _process_device_incoming(
            device.id,
            [
                ("gba", "bad.srm", "/sync/watched-deck/incoming/gba/bad.srm"),
                ("gba", "ok.srm", "/sync/watched-deck/incoming/gba/ok.srm"),
            ],
        )

        [session] = self._sessions(device)
        assert (session.operations_completed, session.operations_failed) == (1, 1)
        error_call = emitted["error"].call_args
        assert error_call is not None
        assert error_call.kwargs["error_message"] == "1 file(s) failed to process"
        emitted["completed"].assert_called_once()

    @pytest.mark.parametrize(
        ("sync_mode", "sync_enabled"),
        [(SyncMode.PUSH_PULL, True), (SyncMode.FILE_TRANSFER, False)],
        ids=["push_pull_device", "sync_disabled"],
    )
    def test_a_device_not_syncing_by_file_transfer_is_ignored(
        self,
        admin_user: User,
        emitted,
        process_file,
        sync_mode: SyncMode,
        sync_enabled: bool,
    ):
        from sync_watcher import _process_device_incoming

        device = self._device(admin_user, sync_mode, sync_enabled)

        _process_device_incoming(device.id, self.FILES)

        process_file.assert_not_called()
        assert self._sessions(device) == []

    def test_an_unknown_device_is_ignored(self, emitted, process_file):
        from sync_watcher import _process_device_incoming

        _process_device_incoming("no-such-device", self.FILES)

        process_file.assert_not_called()
        emitted["started"].assert_not_called()


class TestProcessIncomingFileOutcomes:
    @pytest.fixture
    def device(self, admin_user: User) -> Device:
        return db_device_handler.add_device(
            Device(
                id="watcher-outcome-dev",
                user_id=admin_user.id,
                sync_mode=SyncMode.FILE_TRANSFER,
                sync_enabled=True,
            )
        )

    def test_a_conflict_moves_the_file_aside_and_reports_it(
        self,
        sync_root: Path,
        device: Device,
        admin_user: User,
        rom: Rom,
        platform: Platform,
    ):
        from sync_watcher import _process_incoming_file

        incoming = _incoming(sync_root, device.id, platform.fs_slug, "clash.sav")
        save = make_save(
            rom,
            admin_user,
            "clash.sav",
            emulator="test_emulator",
            slot="autosave",
            file_path=f"{platform.slug}/saves/test_emulator",
            content_hash="server_hash",
        )

        with (
            patch("sync_watcher.compare_save_state") as compare,
            patch("endpoints.sockets.sync.emit_sync_conflict") as emit_conflict,
        ):
            compare.return_value = MagicMock(action="conflict", reason="both changed")
            _process_incoming_file(
                device=device,
                session_id=1,
                platform_slug=platform.fs_slug,
                filename="clash.sav",
                full_path=incoming,
            )

        moved = sync_root / device.id / "conflicts" / platform.fs_slug / "clash.sav"
        assert moved.read_bytes() == b"device bytes"
        assert not os.path.exists(incoming)
        conflict_call = emit_conflict.call_args
        assert conflict_call is not None
        kwargs = conflict_call.kwargs
        assert (kwargs["rom_id"], kwargs["reason"]) == (save.rom_id, "both changed")
        assert kwargs["rom_name"] == (rom.name or rom.fs_name)

    def test_a_newer_device_copy_of_a_held_save_waits_as_a_conflict(
        self,
        sync_root: Path,
        device: Device,
        admin_user: User,
        rom: Rom,
        platform: Platform,
    ):
        from sync_watcher import _process_incoming_file

        incoming = _incoming(sync_root, device.id, platform.fs_slug, "held.sav")
        save = make_save(
            rom,
            admin_user,
            "held.sav",
            emulator="test_emulator",
            slot="autosave",
            file_path=f"{platform.slug}/saves/test_emulator",
            content_hash="server_hash",
        )

        with (
            patch("sync_watcher.compare_save_state") as compare,
            patch("handler.database.db_snapshot_handler.is_frozen", return_value=True),
            patch("sync_watcher.fs_asset_handler.write_file") as write_file,
            patch("endpoints.sockets.sync.emit_sync_conflict") as emit_conflict,
        ):
            compare.return_value = MagicMock(action="upload", reason=None)
            _process_incoming_file(
                device=device,
                session_id=1,
                platform_slug=platform.fs_slug,
                filename="held.sav",
                full_path=incoming,
            )

        moved = sync_root / device.id / "conflicts" / platform.fs_slug / "held.sav"
        assert moved.read_bytes() == b"device bytes"
        write_file.assert_not_called()
        kept = db_save_handler.get_save(admin_user.id, save.id)
        assert kept is not None and kept.content_hash == "server_hash"
        assert emit_conflict.call_args.kwargs["reason"] == (
            "the save belongs to a sync channel"
        )

    def test_an_unknown_platform_leaves_the_file_alone(
        self, sync_root: Path, device: Device
    ):
        from sync_watcher import _process_incoming_file

        incoming = _incoming(sync_root, device.id, "not-a-platform", "a.sav")

        with patch("sync_watcher.compare_save_state") as compare:
            _process_incoming_file(
                device=device,
                session_id=1,
                platform_slug="not-a-platform",
                filename="a.sav",
                full_path=incoming,
            )

        compare.assert_not_called()
        assert os.path.exists(incoming)

    def test_a_file_without_a_matching_save_is_left_alone(
        self, sync_root: Path, device: Device, platform: Platform
    ):
        from sync_watcher import _process_incoming_file

        incoming = _incoming(sync_root, device.id, platform.fs_slug, "new.sav")

        with patch("sync_watcher.compare_save_state") as compare:
            _process_incoming_file(
                device=device,
                session_id=1,
                platform_slug=platform.fs_slug,
                filename="new.sav",
                full_path=incoming,
            )

        compare.assert_not_called()
        assert os.path.exists(incoming)
