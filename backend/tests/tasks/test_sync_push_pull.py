"""Tests for SyncPushPullTask initialization and configuration."""

from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tests.factories import make_save

from endpoints.sockets import sync as sync_sockets
from handler.database import (
    db_deleted_asset_handler,
    db_device_handler,
    db_device_save_sync_handler,
    db_save_handler,
    db_sync_session_handler,
)
from handler.sync.ssh_handler import RemoteSaveInfo
from models.assets import Save
from models.device import Device, SyncMode
from models.platform import Platform
from models.rom import Rom
from models.sync_session import SyncSessionStatus
from models.user import User
from tasks import sync_push_pull_task as push_pull
from tasks.registry import SYNC_PUSH_PULL_SPEC
from tasks.sync_push_pull_task import (
    SyncPushPullTask,
    _process_remote_save,
    _push_missing_saves,
    _sync_device,
    run_push_pull_sync,
    sync_push_pull_task,
)
from tasks.tasks import PeriodicTask, TaskType


class TestSyncPushPullTaskInit:
    @pytest.fixture
    def task(self):
        return SyncPushPullTask()

    def test_init(self, task: SyncPushPullTask):
        assert task.spec.title == "Push-Pull Sync"
        assert task.spec.description == "Sync saves with devices via SSH/SFTP"
        assert task.spec.task_type == TaskType.SYNC

    def test_is_periodic_task(self, task: SyncPushPullTask):
        assert isinstance(task, PeriodicTask)

    def test_module_singleton_exists(self):
        assert sync_push_pull_task is not None
        assert isinstance(sync_push_pull_task, SyncPushPullTask)

    def test_cron_string_set(self, task: SyncPushPullTask):
        assert task.spec.cron_string is not None


class TestRunPushPullSync:
    @patch(
        "tasks.sync_push_pull_task.SYNC_PUSH_PULL_SPEC",
        replace(SYNC_PUSH_PULL_SPEC, enabled=False),
    )
    async def test_run_disabled_returns_disabled(self):
        from tasks.sync_push_pull_task import run_push_pull_sync

        result = await run_push_pull_sync()
        assert result["status"] == "disabled"

    @patch(
        "tasks.sync_push_pull_task.SYNC_PUSH_PULL_SPEC",
        replace(SYNC_PUSH_PULL_SPEC, enabled=True),
    )
    @patch("tasks.sync_push_pull_task.db_device_handler")
    async def test_run_no_devices(self, mock_device_handler):
        from tasks.sync_push_pull_task import run_push_pull_sync

        mock_device_handler.get_all_devices_by_sync_mode.return_value = []

        result = await run_push_pull_sync()
        assert result["status"] == "no_devices"

    @patch(
        "tasks.sync_push_pull_task.SYNC_PUSH_PULL_SPEC",
        replace(SYNC_PUSH_PULL_SPEC, enabled=True),
    )
    @patch("tasks.sync_push_pull_task.db_device_handler")
    async def test_run_device_not_found(self, mock_device_handler):
        from tasks.sync_push_pull_task import run_push_pull_sync

        mock_device_handler.get_device_by_id.return_value = None

        result = await run_push_pull_sync(device_id="nonexistent")
        assert result["status"] == "error"
        assert "not found" in result["message"]

    @patch(
        "tasks.sync_push_pull_task.SYNC_PUSH_PULL_SPEC",
        replace(SYNC_PUSH_PULL_SPEC, enabled=False),
    )
    async def test_run_force_override(self):
        from tasks.sync_push_pull_task import run_push_pull_sync

        with patch("tasks.sync_push_pull_task.db_device_handler") as mock_handler:
            mock_handler.get_device_by_id.return_value = None
            result = await run_push_pull_sync(device_id="test", force=True)
            assert result["status"] == "error"  # Device not found, but didn't skip


class TestNullSlotLeakInProcessRemoteSave:
    """Bug R1a: `_process_remote_save` selects the first save with matching
    filename, including null-slot archival saves. This mirrors the negotiate
    Invariant 2 leak — archival saves must never participate in device sync.
    """

    @pytest.fixture
    def device(self, admin_user: User) -> Device:
        return db_device_handler.add_device(
            Device(
                id="pp-dev-1",
                user_id=admin_user.id,
                sync_mode=SyncMode.PUSH_PULL,
                sync_enabled=True,
                sync_config={"ssh_host": "1.2.3.4"},
            )
        )

    async def test_remote_filename_does_not_match_null_slot_archival(
        self,
        device: Device,
        admin_user: User,
        rom: Rom,
        platform: Platform,
        archival_save: Save,
    ):
        """Only an archival (null-slot) save exists with the colliding name.
        A remote file with that filename must NOT be paired with the archival
        row. The function should treat this as 'no matching server save' and
        return 'skipped' (it certainly must not write to the archival save).
        """
        remote_save = RemoteSaveInfo(
            path=f"/remote/{platform.fs_slug}/{archival_save.file_name}",
            file_name=archival_save.file_name,
            platform_slug=platform.fs_slug,
            file_size=999,
            mtime=datetime.now(timezone.utc),
        )

        ssh = MagicMock()
        ssh.download_save = AsyncMock(
            return_value=("/tmp/should_not_be_called", "deadbeef")
        )
        ssh.upload_save = AsyncMock()

        with patch("tasks.sync_push_pull_task.get_ssh_sync_handler", return_value=ssh):
            action = await _process_remote_save(
                device, conn=MagicMock(), remote_save=remote_save, session_id=1
            )

        # Archival rows must not be selected as a sync target.
        assert action == "skipped"
        # The archival row's bytes must be untouched.
        refreshed = db_save_handler.get_save(user_id=admin_user.id, id=archival_save.id)
        assert refreshed is not None
        assert refreshed.content_hash == archival_save.content_hash
        assert refreshed.file_size_bytes == archival_save.file_size_bytes
        # And nothing should have been downloaded from the device for this row.
        ssh.download_save.assert_not_called()

    async def test_remote_filename_matches_slotted_save_when_archival_collides(
        self,
        device: Device,
        admin_user: User,
        rom: Rom,
        platform: Platform,
        save: Save,
    ):
        """When both an archival and a slotted save share the filename, the
        function must pick the slotted save, not the archival row that appears
        first in the unfiltered query result.
        """
        # Create an additional archival (null-slot) save with the same filename
        # as the slotted `save` fixture (test_save.sav). Insert it FIRST so the
        # unfiltered iteration order favours it under the current bug.
        archival = make_save(
            rom,
            admin_user,
            save.file_name,
            emulator=save.emulator,
            slot=None,
            file_path=save.file_path,
            file_size_bytes=42,
            content_hash="archival_hash_unique",
        )

        remote_save = RemoteSaveInfo(
            path=f"/remote/{platform.fs_slug}/{save.file_name}",
            file_name=save.file_name,
            platform_slug=platform.fs_slug,
            file_size=1,
            mtime=datetime.now(timezone.utc),
        )

        ssh = MagicMock()
        ssh.download_save = AsyncMock(
            return_value=("/tmp/should_not_matter", save.content_hash or "x")
        )
        ssh.upload_save = AsyncMock()

        with (
            patch("tasks.sync_push_pull_task.get_ssh_sync_handler", return_value=ssh),
            patch("tasks.sync_push_pull_task.fs_asset_handler"),
            patch("tasks.sync_push_pull_task.compare_save_state") as mock_cmp,
            patch("tasks.sync_push_pull_task.AnyioPath") as mock_anyio_path,
        ):
            mock_cmp.return_value = MagicMock(action="no_op", reason=None)
            mock_anyio_path.return_value.exists = AsyncMock(return_value=False)
            await _process_remote_save(
                device, conn=MagicMock(), remote_save=remote_save, session_id=1
            )

            # compare_save_state should have been called with the SLOTTED save's
            # hash, not the archival one. The bug picks the archival because it
            # appears first in the unfiltered iteration.
            kwargs = mock_cmp.call_args.kwargs
            assert (
                kwargs["server_hash"] != "archival_hash_unique"
            ), "archival null-slot save leaked into push-pull match path"

        # Archival row must remain untouched regardless.
        refreshed = db_save_handler.get_save(user_id=admin_user.id, id=archival.id)
        assert refreshed is not None
        assert refreshed.content_hash == "archival_hash_unique"

    async def test_a_version_removed_since_the_device_wrote_it_is_replaced(
        self, device: Device, admin_user: User, platform: Platform, save: Save
    ):
        """Newer than the server's save by its timestamp, yet lost since it was written."""
        assert save.slot
        db_save_handler.update_save(
            save.id, {"updated_at": datetime(2020, 1, 1, tzinfo=timezone.utc)}
        )
        db_deleted_asset_handler.record_deletion(
            admin_user.id, save.rom_id, save.slot, "removed_here"
        )
        remote_save = RemoteSaveInfo(
            path=f"/remote/{platform.fs_slug}/{save.file_name}",
            file_name=save.file_name,
            platform_slug=platform.fs_slug,
            file_size=1,
            mtime=datetime(2021, 1, 1, tzinfo=timezone.utc),
        )
        ssh = MagicMock()
        ssh.download_save = AsyncMock(return_value=("/tmp/unused", "removed_here"))
        ssh.upload_save = AsyncMock()

        with (
            patch("tasks.sync_push_pull_task.get_ssh_sync_handler", return_value=ssh),
            patch("tasks.sync_push_pull_task.fs_asset_handler"),
            patch("tasks.sync_push_pull_task.AnyioPath") as mock_anyio_path,
        ):
            mock_anyio_path.return_value.exists = AsyncMock(return_value=False)
            action = await _process_remote_save(
                device, conn=MagicMock(), remote_save=remote_save, session_id=1
            )

        assert action == "pushed"
        ssh.upload_save.assert_awaited_once()


class TestProcessRemoteSaveConflict:
    async def test_conflict_names_the_matched_rom(
        self, admin_user: User, rom: Rom, platform: Platform, save: Save
    ):
        device = db_device_handler.add_device(
            Device(
                id="pp-dev-conflict",
                user_id=admin_user.id,
                sync_mode=SyncMode.PUSH_PULL,
                sync_enabled=True,
                sync_config={"ssh_host": "1.2.3.4"},
            )
        )
        remote_save = RemoteSaveInfo(
            path=f"/remote/{platform.fs_slug}/{save.file_name}",
            file_name=save.file_name,
            platform_slug=platform.fs_slug,
            file_size=1,
            mtime=datetime.now(timezone.utc),
        )
        ssh = MagicMock()
        ssh.download_save = AsyncMock(return_value=("/tmp/pp-conflict", "remote"))

        with (
            patch("tasks.sync_push_pull_task.get_ssh_sync_handler", return_value=ssh),
            patch("tasks.sync_push_pull_task.compare_save_state") as mock_cmp,
            patch("tasks.sync_push_pull_task.AnyioPath") as mock_anyio_path,
            patch(
                "endpoints.sockets.sync.emit_sync_conflict", new_callable=AsyncMock
            ) as emit,
        ):
            mock_cmp.return_value = MagicMock(action="conflict", reason="both changed")
            mock_anyio_path.return_value.exists = AsyncMock(return_value=False)
            action = await _process_remote_save(
                device, conn=MagicMock(), remote_save=remote_save, session_id=5
            )

        assert action == "conflict"
        emit.assert_awaited_once_with(
            user_id=admin_user.id,
            device_id=device.id,
            session_id=5,
            file_name=save.file_name,
            rom_id=rom.id,
            rom_name="test_rom",
            reason="both changed",
        )


class TestNullSlotLeakInPushMissingSaves:
    """Bug R1b: `_push_missing_saves` iterates every Save for the platform,
    including null-slot archival rows, and uploads them to the device.
    """

    @pytest.fixture
    def device(self, admin_user: User) -> Device:
        return db_device_handler.add_device(
            Device(
                id="pp-dev-2",
                user_id=admin_user.id,
                sync_mode=SyncMode.PUSH_PULL,
                sync_enabled=True,
                sync_config={"ssh_host": "1.2.3.4"},
            )
        )

    async def test_archival_save_is_not_pushed_to_device(
        self,
        device: Device,
        admin_user: User,
        platform: Platform,
        save: Save,
        archival_save: Save,
    ):
        """Only the slotted save should be uploaded. The null-slot archival
        save must never be pushed to a device under push-pull sync.
        """
        ssh = MagicMock()
        ssh.upload_save = AsyncMock()

        save_directories = [
            {"platform_slug": platform.fs_slug, "path": "/remote/saves"}
        ]
        # Empty remote_saves means every server save would be considered "missing".
        with (
            patch("tasks.sync_push_pull_task.get_ssh_sync_handler", return_value=ssh),
            patch("tasks.sync_push_pull_task.fs_asset_handler") as mock_assets,
        ):
            mock_assets.validate_path.side_effect = lambda p: f"/server/{p}"
            pushed = await _push_missing_saves(
                device,
                conn=MagicMock(),
                remote_saves=[],
                save_directories=save_directories,
            )

        uploaded_local_paths = [call.args[1] for call in ssh.upload_save.call_args_list]
        # The archival file_name MUST NOT appear in any uploaded path.
        assert not any(
            archival_save.file_name in p for p in uploaded_local_paths
        ), f"archival save {archival_save.file_name} leaked into device push: {uploaded_local_paths}"
        # The slotted save SHOULD have been pushed.
        assert any(
            save.file_name in p for p in uploaded_local_paths
        ), f"slotted save was not pushed: {uploaded_local_paths}"
        # And the upload count should reflect slotted-only.
        assert pushed == (1, 0)


class TestBaselineInProcessRemoteSave:
    """This path hashes the device's file itself, so it can record both halves."""

    @pytest.fixture
    def device(self, admin_user: User) -> Device:
        return db_device_handler.add_device(
            Device(
                id="pp-baseline-dev",
                user_id=admin_user.id,
                sync_mode=SyncMode.PUSH_PULL,
                sync_enabled=True,
                sync_config={"ssh_host": "1.2.3.4"},
            )
        )

    @pytest.fixture
    def local_save_file(self, tmp_path) -> str:
        path = tmp_path / "pp_baseline.sav"
        path.write_bytes(b"remote save bytes")
        return str(path)

    @staticmethod
    def _save(
        admin_user: User, rom: Rom, platform: Platform, content_hash: str
    ) -> Save:
        return make_save(
            rom,
            admin_user,
            "pp_baseline.sav",
            emulator="test_emulator",
            slot="autosave",
            file_path=f"{platform.slug}/saves/test_emulator",
            file_size_bytes=100,
            content_hash=content_hash,
        )

    @staticmethod
    def _remote(platform: Platform) -> RemoteSaveInfo:
        return RemoteSaveInfo(
            path=f"/remote/{platform.fs_slug}/pp_baseline.sav",
            file_name="pp_baseline.sav",
            platform_slug=platform.fs_slug,
            file_size=100,
            mtime=datetime.now(timezone.utc),
        )

    @staticmethod
    def _ssh(local_path: str, remote_hash: str) -> MagicMock:
        ssh = MagicMock()
        ssh.download_save = AsyncMock(return_value=(local_path, remote_hash))
        ssh.upload_save = AsyncMock()
        return ssh

    async def test_comparison_receives_the_recorded_baseline(
        self,
        device: Device,
        admin_user: User,
        rom: Rom,
        platform: Platform,
        local_save_file: str,
    ):
        save = self._save(admin_user, rom, platform, "server_old")
        db_device_save_sync_handler.upsert_sync(
            device.id,
            save.id,
            synced_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
            last_sync_hash="client_at_boundary",
            last_sync_server_hash="server_at_boundary",
        )

        with (
            patch("tasks.sync_push_pull_task.get_ssh_sync_handler") as mock_handler,
            patch("tasks.sync_push_pull_task.compare_save_state") as mock_cmp,
        ):
            mock_handler.return_value = self._ssh(local_save_file, "remote_now")
            mock_cmp.return_value = MagicMock(action="no_op", reason=None)
            await _process_remote_save(
                device,
                conn=MagicMock(),
                remote_save=self._remote(platform),
                session_id=1,
            )

        kwargs = mock_cmp.call_args.kwargs
        assert kwargs["device_last_sync_hash"] == "client_at_boundary"
        assert kwargs["device_last_sync_server_hash"] == "server_at_boundary"

    @pytest.mark.parametrize(
        "server_hash,recorded",
        [("remote_now", "remote_now"), ("server_hash", None)],
    )
    async def test_no_op_records_a_baseline_only_for_identical_content(
        self,
        device: Device,
        admin_user: User,
        rom: Rom,
        platform: Platform,
        local_save_file: str,
        server_hash: str,
        recorded: str | None,
    ):
        """A timestamp-only no-op must not record two different saves as in sync."""
        save = self._save(admin_user, rom, platform, server_hash)

        with (
            patch("tasks.sync_push_pull_task.get_ssh_sync_handler") as mock_handler,
            patch("tasks.sync_push_pull_task.compare_save_state") as mock_cmp,
        ):
            mock_handler.return_value = self._ssh(local_save_file, "remote_now")
            mock_cmp.return_value = MagicMock(action="no_op", reason=None)
            await _process_remote_save(
                device,
                conn=MagicMock(),
                remote_save=self._remote(platform),
                session_id=1,
            )

        sync = db_device_save_sync_handler.get_sync(device.id, save.id)
        assert sync is not None
        assert sync.last_sync_hash == recorded
        assert sync.last_sync_server_hash == recorded

    async def test_upload_records_both_halves_as_the_remote_hash(
        self,
        device: Device,
        admin_user: User,
        rom: Rom,
        platform: Platform,
        local_save_file: str,
    ):
        save = self._save(admin_user, rom, platform, "server_old")

        with (
            patch("tasks.sync_push_pull_task.get_ssh_sync_handler") as mock_handler,
            patch("tasks.sync_push_pull_task.compare_save_state") as mock_cmp,
            patch("tasks.sync_push_pull_task.fs_asset_handler") as mock_assets,
        ):
            mock_assets.write_file = AsyncMock()
            mock_assets.unrecorded_hash = AsyncMock(return_value=None)
            mock_handler.return_value = self._ssh(local_save_file, "remote_now")
            mock_cmp.return_value = MagicMock(action="upload", reason=None)
            await _process_remote_save(
                device,
                conn=MagicMock(),
                remote_save=self._remote(platform),
                session_id=1,
            )

        sync = db_device_save_sync_handler.get_sync(device.id, save.id)
        assert sync is not None
        assert sync.last_sync_hash == "remote_now"
        assert sync.last_sync_server_hash == "remote_now"

    async def test_download_records_the_pushed_file_as_both_halves(
        self,
        device: Device,
        admin_user: User,
        rom: Rom,
        platform: Platform,
        local_save_file: str,
    ):
        save = self._save(admin_user, rom, platform, "server_new")

        with (
            patch("tasks.sync_push_pull_task.get_ssh_sync_handler") as mock_handler,
            patch("tasks.sync_push_pull_task.compare_save_state") as mock_cmp,
            patch("tasks.sync_push_pull_task.fs_asset_handler"),
        ):
            mock_handler.return_value = self._ssh(local_save_file, "remote_old")
            mock_cmp.return_value = MagicMock(action="download", reason=None)
            await _process_remote_save(
                device,
                conn=MagicMock(),
                remote_save=self._remote(platform),
                session_id=1,
            )

        sync = db_device_save_sync_handler.get_sync(device.id, save.id)
        assert sync is not None
        assert sync.last_sync_hash == "server_new"
        assert sync.last_sync_server_hash == "server_new"

    async def test_conflict_records_nothing(
        self,
        device: Device,
        admin_user: User,
        rom: Rom,
        platform: Platform,
        local_save_file: str,
    ):
        save = self._save(admin_user, rom, platform, "server_hash")
        db_device_save_sync_handler.upsert_sync(
            device.id,
            save.id,
            synced_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
            last_sync_hash="client_at_boundary",
            last_sync_server_hash="server_at_boundary",
        )

        with (
            patch("tasks.sync_push_pull_task.get_ssh_sync_handler") as mock_handler,
            patch("tasks.sync_push_pull_task.compare_save_state") as mock_cmp,
        ):
            mock_handler.return_value = self._ssh(local_save_file, "remote_now")
            mock_cmp.return_value = MagicMock(action="conflict", reason="both changed")
            action = await _process_remote_save(
                device,
                conn=MagicMock(),
                remote_save=self._remote(platform),
                session_id=1,
            )

        assert action == "conflict"
        sync = db_device_save_sync_handler.get_sync(device.id, save.id)
        assert sync is not None
        assert sync.last_sync_hash == "client_at_boundary"
        assert sync.last_sync_server_hash == "server_at_boundary"

    async def test_push_missing_saves_records_the_pushed_file_as_both_halves(
        self,
        device: Device,
        admin_user: User,
        rom: Rom,
        platform: Platform,
    ):
        save = self._save(admin_user, rom, platform, "server_hash")

        with (
            patch("tasks.sync_push_pull_task.get_ssh_sync_handler") as mock_handler,
            patch("tasks.sync_push_pull_task.fs_asset_handler") as mock_assets,
        ):
            mock_handler.return_value = self._ssh("/tmp/unused.sav", "unused")
            mock_assets.validate_path.side_effect = lambda p: f"/server/{p}"
            pushed = await _push_missing_saves(
                device,
                conn=MagicMock(),
                remote_saves=[],
                save_directories=[
                    {"platform_slug": platform.fs_slug, "path": "/remote/saves"}
                ],
            )

        assert pushed == (1, 0)

        sync = db_device_save_sync_handler.get_sync(device.id, save.id)
        assert sync is not None
        assert sync.last_sync_hash == "server_hash"
        assert sync.last_sync_server_hash == "server_hash"

    async def test_push_missing_saves_counts_a_failed_upload(
        self,
        device: Device,
        admin_user: User,
        rom: Rom,
        platform: Platform,
    ):
        self._save(admin_user, rom, platform, "server_hash")
        ssh = self._ssh("/tmp/unused.sav", "unused")
        ssh.upload_save = AsyncMock(side_effect=OSError("device full"))

        with (
            patch("tasks.sync_push_pull_task.get_ssh_sync_handler", return_value=ssh),
            patch("tasks.sync_push_pull_task.fs_asset_handler") as mock_assets,
        ):
            mock_assets.validate_path.side_effect = lambda p: f"/server/{p}"
            result = await _push_missing_saves(
                device,
                conn=MagicMock(),
                remote_saves=[],
                save_directories=[
                    {"platform_slug": platform.fs_slug, "path": "/remote/saves"}
                ],
            )

        assert result == (0, 1)


def _remote(file_name: str) -> RemoteSaveInfo:
    return RemoteSaveInfo(
        path=f"/saves/gba/{file_name}",
        file_name=file_name,
        platform_slug="gba",
        file_size=1,
        mtime=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class TestSyncDevice:
    SAVE_DIRECTORIES = [{"platform_slug": "gba", "path": "/saves/gba"}]

    @pytest.fixture
    def device(self, admin_user: User) -> Device:
        return db_device_handler.add_device(
            Device(
                id="push-pull-deck",
                user_id=admin_user.id,
                sync_mode=SyncMode.PUSH_PULL,
                sync_enabled=True,
                sync_config={
                    "ssh_host": "deck.local",
                    "save_directories": self.SAVE_DIRECTORIES,
                },
            )
        )

    @pytest.fixture
    def conn(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def ssh(self, mocker, conn: MagicMock) -> MagicMock:
        handler = MagicMock()
        handler.connect = AsyncMock(return_value=conn)
        handler.list_remote_saves = AsyncMock(return_value=[])
        mocker.patch.object(push_pull, "get_ssh_sync_handler", return_value=handler)
        return handler

    @pytest.fixture
    def emitted(self, mocker) -> dict[str, AsyncMock]:
        return {
            name: mocker.patch.object(sync_sockets, f"emit_sync_{name}", AsyncMock())
            for name in ("started", "progress", "completed", "error")
        }

    @pytest.fixture
    def process(self, mocker):
        return mocker.patch.object(
            push_pull, "_process_remote_save", AsyncMock(return_value="pulled")
        )

    @pytest.fixture
    def push_missing(self, mocker):
        return mocker.patch.object(
            push_pull, "_push_missing_saves", AsyncMock(return_value=(0, 0))
        )

    @staticmethod
    def _sessions(device: Device):
        return db_sync_session_handler.get_sessions(
            user_id=device.user_id, device_id=device.id
        )

    async def test_syncs_each_remote_save_and_pushes_the_missing_ones(
        self, device, ssh, conn, emitted, process, push_missing
    ):
        ssh.list_remote_saves.return_value = [_remote("a.srm"), _remote("b.srm")]
        process.side_effect = ["pulled", "pushed"]
        push_missing.return_value = (1, 0)

        result = await _sync_device(device)

        assert result == {
            "device_id": device.id,
            "status": "completed",
            "completed": 3,
            "failed": 0,
        }
        ssh.connect.assert_awaited_once_with(device.sync_config, device_id=device.id)
        ssh.list_remote_saves.assert_awaited_once_with(conn, self.SAVE_DIRECTORIES)
        [session] = self._sessions(device)
        assert session.status == SyncSessionStatus.COMPLETED
        assert (session.operations_planned, session.operations_completed) == (3, 3)
        assert emitted["progress"].await_count == 2
        emitted["completed"].assert_awaited_once()
        emitted["error"].assert_not_awaited()
        conn.close.assert_called_once()
        refreshed = db_device_handler.get_device_by_id(device.id)
        assert refreshed and refreshed.last_seen is not None

    async def test_a_failing_save_is_counted_and_the_rest_still_sync(
        self, device, ssh, conn, emitted, process, push_missing
    ):
        ssh.list_remote_saves.return_value = [_remote("bad.srm"), _remote("ok.srm")]
        process.side_effect = [OSError("disk full"), "pushed"]

        result = await _sync_device(device)

        assert (result["completed"], result["failed"]) == (1, 1)
        assert process.await_count == 2
        [session] = self._sessions(device)
        assert session.status == SyncSessionStatus.COMPLETED
        assert session.operations_failed == 1

    async def test_a_failed_push_of_a_missing_save_is_counted(
        self, device, ssh, emitted, process, push_missing
    ):
        ssh.list_remote_saves.return_value = [_remote("a.srm")]
        push_missing.return_value = (1, 2)

        result = await _sync_device(device)

        assert (result["completed"], result["failed"]) == (2, 2)
        [session] = self._sessions(device)
        assert session.operations_planned == 4
        assert (session.operations_completed, session.operations_failed) == (2, 2)

    async def test_a_connection_failure_fails_the_session(
        self, device, ssh, emitted, process
    ):
        ssh.connect.side_effect = OSError("host unreachable")

        result = await _sync_device(device)

        assert result == {
            "device_id": device.id,
            "status": "connection_failed",
            "error": "host unreachable",
        }
        [session] = self._sessions(device)
        assert session.status == SyncSessionStatus.FAILED
        assert session.error_message == "host unreachable"
        emitted["error"].assert_awaited_once()
        process.assert_not_awaited()

    async def test_a_listing_failure_fails_the_session_and_closes_the_connection(
        self, device, ssh, conn, emitted
    ):
        ssh.list_remote_saves.side_effect = OSError("sftp subsystem missing")

        result = await _sync_device(device)

        assert result["status"] == "failed"
        [session] = self._sessions(device)
        assert session.status == SyncSessionStatus.FAILED
        emitted["error"].assert_awaited_once()
        emitted["completed"].assert_not_awaited()
        conn.close.assert_called_once()

    async def test_without_save_directories_there_is_nothing_to_do(
        self, device, ssh, conn, emitted
    ):
        db_device_handler.update_device(
            device_id=device.id,
            user_id=device.user_id,
            data={"sync_config": {"ssh_host": "deck.local"}},
        )
        bare = db_device_handler.get_device_by_id(device.id)
        assert bare

        result = await _sync_device(bare)

        assert result == {"device_id": device.id, "status": "no_directories"}
        ssh.list_remote_saves.assert_not_awaited()
        [session] = self._sessions(device)
        assert session.status == SyncSessionStatus.COMPLETED
        conn.close.assert_called_once()

    async def test_without_a_host_nothing_is_attempted(self, device, ssh, emitted):
        db_device_handler.update_device(
            device_id=device.id, user_id=device.user_id, data={"sync_config": {}}
        )
        hostless = db_device_handler.get_device_by_id(device.id)
        assert hostless

        result = await _sync_device(hostless)

        assert result["status"] == "error"
        ssh.connect.assert_not_awaited()
        assert self._sessions(device) == []

    async def test_reuses_the_session_the_trigger_created(
        self, device, ssh, emitted, process, push_missing
    ):
        queued = db_sync_session_handler.create_session(
            device_id=device.id, user_id=device.user_id
        )

        await _sync_device(device, session_id=queued.id)

        [session] = self._sessions(device)
        assert session.id == queued.id
        assert session.status == SyncSessionStatus.COMPLETED

    async def test_an_unknown_session_gets_a_new_one(
        self, device, ssh, emitted, process, push_missing
    ):
        await _sync_device(device, session_id=999_999)

        [session] = self._sessions(device)
        assert session.id != 999_999
        assert session.status == SyncSessionStatus.COMPLETED


class TestRunPushPullSyncDevices:
    @pytest.fixture
    def sync_device(self, mocker):
        return mocker.patch.object(
            push_pull, "_sync_device", AsyncMock(return_value={"status": "completed"})
        )

    def _device(self, user: User, device_id: str, enabled: bool) -> Device:
        return db_device_handler.add_device(
            Device(
                id=device_id,
                user_id=user.id,
                sync_mode=SyncMode.PUSH_PULL,
                sync_enabled=enabled,
            )
        )

    async def test_syncs_only_enabled_push_pull_devices(
        self, admin_user: User, sync_device: AsyncMock
    ):
        self._device(admin_user, "on", enabled=True)
        self._device(admin_user, "off", enabled=False)

        result = await run_push_pull_sync(force=True)

        assert result["status"] == "completed"
        assert [c.args[0].id for c in sync_device.await_args_list] == ["on"]

    async def test_a_named_device_passes_its_session_along(
        self, admin_user: User, sync_device: AsyncMock
    ):
        self._device(admin_user, "deck", enabled=True)

        await run_push_pull_sync(device_id="deck", session_id=7, force=True)

        call = sync_device.await_args
        assert call is not None
        assert (call.args[0].id, call.kwargs["session_id"]) == ("deck", 7)
