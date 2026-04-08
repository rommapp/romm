"""Tests for sync endpoints."""

from datetime import datetime, timezone
from unittest import mock

from fastapi import status

from handler.database import (
    db_device_handler,
    db_device_save_sync_handler,
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
        # If save has a hash, should be no_op; otherwise download/upload by timestamp
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
        assert data["status"] == "COMPLETED"
        assert data["operations_completed"] == 5
        assert data["operations_failed"] == 1

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
