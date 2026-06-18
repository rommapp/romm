"""Tests for sync endpoints."""

import os
from datetime import datetime, timedelta, timezone
from io import BytesIO
from unittest import mock

from fastapi import status

from handler.database import (
    db_device_handler,
    db_device_save_sync_handler,
    db_play_session_handler,
    db_save_handler,
    db_sync_session_handler,
)
from models.assets import Save
from models.device import Device, SyncMode
from models.rom import Rom
from models.user import User


class TestSyncNegotiate:
    def test_negotiate_new_client_save(
        self, client, access_token: str, admin_user: User, rom: Rom
    ):
        """Client has a save the server doesn't -> upload."""
        device = db_device_handler.add_device(
            Device(id="neg-dev-1", user_id=admin_user.id, sync_enabled=True)
        )

        response = client.post(
            "/api/sync/negotiate",
            json={
                "device_id": device.id,
                "saves": [
                    {
                        "rom_id": rom.id,
                        "file_name": "new_save.sav",
                        "updated_at": "2026-01-10T00:00:00Z",
                        "file_size_bytes": 1024,
                    }
                ],
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_upload"] == 1
        assert data["operations"][0]["action"] == "upload"

    def test_negotiate_server_has_save_client_doesnt(
        self, client, access_token: str, admin_user: User, save: Save
    ):
        """Server has a save the client doesn't mention -> download."""
        device = db_device_handler.add_device(
            Device(id="neg-dev-2", user_id=admin_user.id, sync_enabled=True)
        )

        response = client.post(
            "/api/sync/negotiate",
            json={
                "device_id": device.id,
                "saves": [],
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_download"] >= 1

    def test_negotiate_identical_hashes(
        self, client, access_token: str, admin_user: User, rom: Rom, save: Save
    ):
        """Matching hash -> no_op."""
        device = db_device_handler.add_device(
            Device(id="neg-dev-3", user_id=admin_user.id, sync_enabled=True)
        )

        response = client.post(
            "/api/sync/negotiate",
            json={
                "device_id": device.id,
                "saves": [
                    {
                        "rom_id": save.rom_id,
                        "file_name": save.file_name,
                        "slot": save.slot,
                        "content_hash": save.content_hash,
                        "updated_at": save.updated_at.isoformat(),
                        "file_size_bytes": 100,
                    }
                ],
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Fixture save has no content_hash; hash-match no_op is covered by test_negotiate_matches_untagged_client_to_tagged_server_saves
        assert "session_id" in data

    def test_negotiate_device_not_found(self, client, access_token: str):
        response = client.post(
            "/api/sync/negotiate",
            json={"device_id": "nonexistent", "saves": []},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_negotiate_sync_disabled(self, client, access_token: str, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="neg-dev-disabled", user_id=admin_user.id, sync_enabled=False)
        )

        response = client.post(
            "/api/sync/negotiate",
            json={"device_id": device.id, "saves": []},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_negotiate_creates_session(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(id="neg-dev-session", user_id=admin_user.id, sync_enabled=True)
        )

        response = client.post(
            "/api/sync/negotiate",
            json={"device_id": device.id, "saves": []},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "session_id" in data
        assert data["session_id"] > 0


class TestSyncSessions:
    def test_complete_session(self, client, access_token: str, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="session-dev-1", user_id=admin_user.id)
        )
        sync_session = db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )

        response = client.post(
            f"/api/sync/sessions/{sync_session.id}/complete",
            json={"operations_completed": 5, "operations_failed": 1},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["session"]["status"] == "COMPLETED"
        assert data["session"]["operations_completed"] == 5
        assert data["session"]["operations_failed"] == 1
        assert data["play_session_ingest"] is None

    def test_complete_session_not_found(self, client, access_token: str):
        response = client.post(
            "/api/sync/sessions/99999/complete",
            json={"operations_completed": 0, "operations_failed": 0},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_complete_already_completed_session(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(id="session-dev-completed", user_id=admin_user.id)
        )
        sync_session = db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )
        db_sync_session_handler.complete_session(session_id=sync_session.id)

        response = client.post(
            f"/api/sync/sessions/{sync_session.id}/complete",
            json={"operations_completed": 0, "operations_failed": 0},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_sessions(self, client, access_token: str, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="session-dev-list", user_id=admin_user.id)
        )
        db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )
        db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )

        response = client.get(
            "/api/sync/sessions",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

    def test_list_sessions_filter_by_device(
        self, client, access_token: str, admin_user: User
    ):
        dev_a = db_device_handler.add_device(
            Device(id="session-dev-a", user_id=admin_user.id)
        )
        dev_b = db_device_handler.add_device(
            Device(id="session-dev-b", user_id=admin_user.id)
        )
        db_sync_session_handler.create_session(
            device_id=dev_a.id, user_id=admin_user.id
        )
        db_sync_session_handler.create_session(
            device_id=dev_b.id, user_id=admin_user.id
        )

        response = client.get(
            f"/api/sync/sessions?device_id={dev_a.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["device_id"] == dev_a.id

    def test_get_session(self, client, access_token: str, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="session-dev-get", user_id=admin_user.id)
        )
        sync_session = db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )

        response = client.get(
            f"/api/sync/sessions/{sync_session.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == sync_session.id
        assert data["device_id"] == device.id

    def test_get_session_not_found(self, client, access_token: str):
        response = client.get(
            "/api/sync/sessions/99999",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestSyncUserIsolation:
    def test_cannot_negotiate_with_other_users_device(
        self, client, editor_access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(id="admin-sync-dev", user_id=admin_user.id, sync_enabled=True)
        )

        response = client.post(
            "/api/sync/negotiate",
            json={"device_id": device.id, "saves": []},
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_complete_other_users_session(
        self, client, editor_access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(id="admin-session-dev", user_id=admin_user.id)
        )
        sync_session = db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )

        response = client.post(
            f"/api/sync/sessions/{sync_session.id}/complete",
            json={"operations_completed": 0, "operations_failed": 0},
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_sessions_only_return_own(
        self,
        client,
        access_token: str,
        editor_access_token: str,
        admin_user: User,
        editor_user: User,
    ):
        admin_dev = db_device_handler.add_device(
            Device(id="admin-iso-dev", user_id=admin_user.id)
        )
        editor_dev = db_device_handler.add_device(
            Device(id="editor-iso-dev", user_id=editor_user.id)
        )
        db_sync_session_handler.create_session(
            device_id=admin_dev.id, user_id=admin_user.id
        )
        db_sync_session_handler.create_session(
            device_id=editor_dev.id, user_id=editor_user.id
        )

        admin_resp = client.get(
            "/api/sync/sessions",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        editor_resp = client.get(
            "/api/sync/sessions",
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )

        assert len(admin_resp.json()) == 1
        assert admin_resp.json()[0]["device_id"] == admin_dev.id
        assert len(editor_resp.json()) == 1
        assert editor_resp.json()[0]["device_id"] == editor_dev.id


class TestPushPullTrigger:
    def test_trigger_push_pull(self, client, access_token: str, admin_user: User):
        device = db_device_handler.add_device(
            Device(
                id="pp-dev-1",
                user_id=admin_user.id,
                sync_mode=SyncMode.PUSH_PULL,
                sync_enabled=True,
            )
        )

        with mock.patch("endpoints.sync.high_prio_queue") as mock_queue:
            response = client.post(
                f"/api/sync/devices/{device.id}/push-pull",
                headers={"Authorization": f"Bearer {access_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["device_id"] == device.id
        assert data["status"] == "PENDING"
        mock_queue.enqueue.assert_called_once()

    def test_trigger_push_pull_wrong_mode(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(
                id="pp-dev-wrong-mode",
                user_id=admin_user.id,
                sync_mode=SyncMode.API,
                sync_enabled=True,
            )
        )

        response = client.post(
            f"/api/sync/devices/{device.id}/push-pull",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_trigger_push_pull_sync_disabled(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(
                id="pp-dev-disabled",
                user_id=admin_user.id,
                sync_mode=SyncMode.PUSH_PULL,
                sync_enabled=False,
            )
        )

        response = client.post(
            f"/api/sync/devices/{device.id}/push-pull",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_trigger_push_pull_device_not_found(self, client, access_token: str):
        response = client.post(
            "/api/sync/devices/nonexistent/push-pull",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_trigger_push_pull_passes_session_id(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(
                id="pp-dev-sid",
                user_id=admin_user.id,
                sync_mode=SyncMode.PUSH_PULL,
                sync_enabled=True,
            )
        )

        with mock.patch("endpoints.sync.high_prio_queue") as mock_queue:
            response = client.post(
                f"/api/sync/devices/{device.id}/push-pull",
                headers={"Authorization": f"Bearer {access_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_queue.enqueue.call_args
        assert "session_id" in call_kwargs.kwargs


class TestNegotiateAdvanced:
    def test_negotiate_untracked_save_returns_noop(
        self, client, access_token: str, admin_user: User, save: Save
    ):
        device = db_device_handler.add_device(
            Device(id="neg-untrack-dev", user_id=admin_user.id, sync_enabled=True)
        )
        db_device_save_sync_handler.set_untracked(
            device_id=device.id, save_id=save.id, untracked=True
        )

        response = client.post(
            "/api/sync/negotiate",
            json={
                "device_id": device.id,
                "saves": [
                    {
                        "rom_id": save.rom_id,
                        "file_name": save.file_name,
                        "slot": save.slot,
                        "content_hash": "different_hash",
                        "updated_at": "2026-03-01T00:00:00Z",
                        "file_size_bytes": 100,
                    }
                ],
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        noop_ops = [op for op in data["operations"] if op["action"] == "no_op"]
        assert len(noop_ops) >= 1

    def test_negotiate_server_save_not_mentioned_by_client(
        self, client, access_token: str, admin_user: User, save: Save
    ):
        device = db_device_handler.add_device(
            Device(id="neg-miss-dev", user_id=admin_user.id, sync_enabled=True)
        )

        response = client.post(
            "/api/sync/negotiate",
            json={"device_id": device.id, "saves": []},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        download_ops = [op for op in data["operations"] if op["action"] == "download"]
        assert len(download_ops) >= 1
        assert any(op["save_id"] == save.id for op in download_ops)

    def test_negotiate_excludes_archival_null_slot_saves(
        self, client, access_token: str, admin_user: User, archival_save: Save
    ):
        """Null-slot saves (web-UI / archival uploads) must not appear in
        negotiate plans.

        Archival saves are pure backups; clients can opt in to import them
        outside the sync flow. Surfacing them in negotiate as 'download'
        produces phantom operations on every device that's never synced them.
        """
        device = db_device_handler.add_device(
            Device(id="neg-archival-dev", user_id=admin_user.id, sync_enabled=True)
        )

        response = client.post(
            "/api/sync/negotiate",
            json={"device_id": device.id, "saves": []},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        ops_for_archival = [
            op for op in data["operations"] if op.get("save_id") == archival_save.id
        ]
        assert ops_for_archival == [], (
            f"Archival null-slot save unexpectedly surfaced in negotiate: "
            f"{ops_for_archival}"
        )

    def test_negotiate_deleted_by_client_skipped(
        self, client, access_token: str, admin_user: User, save: Save
    ):
        device = db_device_handler.add_device(
            Device(id="neg-del-dev", user_id=admin_user.id, sync_enabled=True)
        )
        db_device_save_sync_handler.upsert_sync(
            device_id=device.id,
            save_id=save.id,
            synced_at=datetime.now(timezone.utc),
        )

        response = client.post(
            "/api/sync/negotiate",
            json={"device_id": device.id, "saves": []},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        ops_for_save = [op for op in data["operations"] if op.get("save_id") == save.id]
        assert len(ops_for_save) == 0

    def test_negotiate_matches_untagged_client_to_tagged_server_saves(
        self, client, access_token: str, admin_user: User, rom: Rom, platform
    ):
        """Spec datetime-tags every slot upload, so a slot accrues many tagged rows and the client reports the untagged canonical name. Pairing must be by (rom_id, slot) on the newest row, else every negotiate yields upload+download forever."""
        device = db_device_handler.add_device(
            Device(id="neg-tagged-dev", user_id=admin_user.id, sync_enabled=True)
        )
        for tag in ("2026-01-01_00-00-00", "2026-02-02_00-00-00"):
            db_save_handler.add_save(
                Save(
                    rom_id=rom.id,
                    user_id=admin_user.id,
                    file_name=f"test_save [{tag}].sav",
                    file_name_no_tags="test_save",
                    file_name_no_ext=f"test_save [{tag}]",
                    file_extension="sav",
                    emulator="test_emulator",
                    slot="autosave",
                    content_hash="HASH_MATCH",
                    file_path=f"{platform.slug}/saves/test_emulator",
                    file_size_bytes=1.0,
                )
            )

        response = client.post(
            "/api/sync/negotiate",
            json={
                "device_id": device.id,
                "saves": [
                    {
                        "rom_id": rom.id,
                        "file_name": "test_save.sav",
                        "slot": "autosave",
                        "content_hash": "HASH_MATCH",
                        "updated_at": "2026-03-01T00:00:00Z",
                        "file_size_bytes": 100,
                    }
                ],
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_upload"] == 0
        assert data["total_download"] == 0
        rom_ops = [op for op in data["operations"] if op["rom_id"] == rom.id]
        assert len(rom_ops) == 1
        assert rom_ops[0]["action"] == "no_op"

    def _upload_autosave(
        self, client, access_token, rom, *, filename, content_hash, device_id
    ):
        """Upload through the real add_save so _apply_datetime_tag runs; scan_save is mocked to echo the server-computed (tagged) file_name, never a hand-authored one."""

        def make_scanned(*, file_name, user, platform_fs_slug, rom_id, emulator):
            return Save(
                file_name=file_name,
                file_name_no_tags=file_name.split(" [")[0],
                file_name_no_ext=os.path.splitext(file_name)[0],
                file_extension="zip",
                file_path=f"{platform_fs_slug}/saves/{emulator or ''}",
                file_size_bytes=100,
                content_hash=content_hash,
            )

        with mock.patch(
            "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
        ), mock.patch(
            "endpoints.saves.fs_asset_handler.remove_file", new_callable=mock.AsyncMock
        ), mock.patch(
            "endpoints.saves.scan_save",
            new=mock.AsyncMock(side_effect=make_scanned),
        ):
            return client.post(
                f"/api/saves?rom_id={rom.id}&slot=autosave&emulator=eden"
                f"&device_id={device_id}",
                files={
                    "saveFile": (
                        filename,
                        BytesIO(b"save bytes"),
                        "application/octet-stream",
                    )
                },
                headers={"Authorization": f"Bearer {access_token}"},
            )

    def _negotiate(self, client, access_token, device_id, saves):
        resp = client.post(
            "/api/sync/negotiate",
            json={"device_id": device_id, "saves": saves},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == status.HTTP_200_OK
        return resp.json()

    @staticmethod
    def _autosave_entry(rom, content_hash):
        return {
            "rom_id": rom.id,
            "file_name": "pokemon_violet.zip",
            "slot": "autosave",
            "content_hash": content_hash,
            "updated_at": "2026-03-01T00:00:00Z",
            "file_size_bytes": 100,
        }

    def test_save_upload_then_negotiate_converges(
        self, client, access_token: str, admin_user: User, rom: Rom, platform
    ):
        """Full round-trip: upload tags the filename (real add_save), then the client reports its untagged canonical name. Must converge to no_op, not re-upload. This is the regression that hand-fed-filename mocks missed."""
        device = db_device_handler.add_device(
            Device(id="conv-rt-dev", user_id=admin_user.id, sync_enabled=True)
        )
        up = self._upload_autosave(
            client,
            access_token,
            rom,
            filename="pokemon_violet.zip",
            content_hash="HASH_RT",
            device_id=device.id,
        )
        assert up.status_code == status.HTTP_200_OK
        stored = up.json()
        assert stored["file_name"] != "pokemon_violet.zip"
        assert " [" in stored["file_name"]

        data = self._negotiate(
            client, access_token, device.id, [self._autosave_entry(rom, "HASH_RT")]
        )
        assert data["total_upload"] == 0
        assert data["total_download"] == 0
        rom_ops = [op for op in data["operations"] if op["rom_id"] == rom.id]
        assert len(rom_ops) == 1
        assert rom_ops[0]["action"] == "no_op"

    def test_three_device_sync_converges(
        self, client, access_token: str, admin_user: User, rom: Rom, platform
    ):
        """A uploads; B and C each download exactly once then converge to no_op. The pre-fix tagged-filename keying made every device upload+download forever -- this is the 3-device scenario done with faithful (untagged client / tagged server) names."""
        device_a = db_device_handler.add_device(
            Device(id="conv-a", user_id=admin_user.id, sync_enabled=True)
        )
        up = self._upload_autosave(
            client,
            access_token,
            rom,
            filename="pokemon_violet.zip",
            content_hash="HASH_3D",
            device_id=device_a.id,
        )
        assert up.status_code == status.HTTP_200_OK
        save_id = up.json()["id"]

        a_data = self._negotiate(
            client, access_token, device_a.id, [self._autosave_entry(rom, "HASH_3D")]
        )
        assert a_data["total_upload"] == 0
        assert a_data["total_download"] == 0

        for dev_id in ("conv-b", "conv-c"):
            dev = db_device_handler.add_device(
                Device(id=dev_id, user_id=admin_user.id, sync_enabled=True)
            )
            first = self._negotiate(client, access_token, dev.id, [])
            downloads = [
                op
                for op in first["operations"]
                if op["action"] == "download" and op["save_id"] == save_id
            ]
            assert len(downloads) == 1
            db_device_save_sync_handler.upsert_sync(
                device_id=dev.id, save_id=save_id, synced_at=datetime.now(timezone.utc)
            )
            second = self._negotiate(
                client, access_token, dev.id, [self._autosave_entry(rom, "HASH_3D")]
            )
            assert second["total_upload"] == 0
            assert second["total_download"] == 0

    def test_complete_failed_session_rejected(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(id="sess-failed-dev", user_id=admin_user.id)
        )
        sync_session = db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )
        db_sync_session_handler.fail_session(sync_session.id, error_message="test")

        response = client.post(
            f"/api/sync/sessions/{sync_session.id}/complete",
            json={"operations_completed": 0, "operations_failed": 0},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_complete_cancelled_session_rejected(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(id="sess-cancel-dev", user_id=admin_user.id)
        )
        db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )
        db_sync_session_handler.cancel_active_sessions(device.id, admin_user.id)

        sessions = db_sync_session_handler.get_sessions(
            admin_user.id, device_id=device.id
        )
        cancelled = sessions[0]

        response = client.post(
            f"/api/sync/sessions/{cancelled.id}/complete",
            json={"operations_completed": 0, "operations_failed": 0},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


def _play_session(rom_id=None, start_offset_hours=-1, duration_minutes=30):
    now = datetime.now(timezone.utc)
    start = now + timedelta(hours=start_offset_hours)
    end = start + timedelta(minutes=duration_minutes)
    return {
        "rom_id": rom_id,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "duration_ms": duration_minutes * 60 * 1000,
    }


class TestSyncCompleteWithPlaySessions:
    def test_complete_with_play_sessions(
        self, client, access_token: str, admin_user: User, rom: Rom
    ):
        device = db_device_handler.add_device(
            Device(id="sync-ps-dev-1", user_id=admin_user.id)
        )
        sync_session = db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )

        response = client.post(
            f"/api/sync/sessions/{sync_session.id}/complete",
            json={
                "operations_completed": 1,
                "operations_failed": 0,
                "play_sessions": [
                    _play_session(rom_id=rom.id, start_offset_hours=-2),
                    _play_session(rom_id=rom.id, start_offset_hours=-4),
                ],
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["session"]["status"] == "COMPLETED"
        assert data["play_session_ingest"] is not None
        assert data["play_session_ingest"]["created_count"] == 2
        assert data["play_session_ingest"]["skipped_count"] == 0

    def test_play_sessions_have_sync_session_id(
        self, client, access_token: str, admin_user: User, rom: Rom
    ):
        device = db_device_handler.add_device(
            Device(id="sync-ps-dev-2", user_id=admin_user.id)
        )
        sync_session = db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )

        client.post(
            f"/api/sync/sessions/{sync_session.id}/complete",
            json={
                "operations_completed": 0,
                "operations_failed": 0,
                "play_sessions": [
                    _play_session(rom_id=rom.id, start_offset_hours=-3),
                ],
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        sessions = db_play_session_handler.get_sessions(
            user_id=admin_user.id, rom_id=rom.id
        )
        assert len(sessions) >= 1
        linked = [s for s in sessions if s.sync_session_id == sync_session.id]
        assert len(linked) == 1

    def test_play_sessions_use_device_from_sync_session(
        self, client, access_token: str, admin_user: User, rom: Rom
    ):
        device = db_device_handler.add_device(
            Device(id="sync-ps-dev-3", user_id=admin_user.id)
        )
        sync_session = db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )

        client.post(
            f"/api/sync/sessions/{sync_session.id}/complete",
            json={
                "operations_completed": 0,
                "operations_failed": 0,
                "play_sessions": [
                    _play_session(rom_id=rom.id, start_offset_hours=-5),
                ],
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        sessions = db_play_session_handler.get_sessions(
            user_id=admin_user.id, rom_id=rom.id
        )
        assert len(sessions) >= 1
        assert sessions[0].device_id == device.id

    def test_complete_without_play_sessions_backward_compatible(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(id="sync-ps-dev-4", user_id=admin_user.id)
        )
        sync_session = db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )

        response = client.post(
            f"/api/sync/sessions/{sync_session.id}/complete",
            json={"operations_completed": 3, "operations_failed": 0},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["session"]["status"] == "COMPLETED"
        assert data["play_session_ingest"] is None
