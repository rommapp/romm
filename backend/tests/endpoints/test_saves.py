from datetime import timedelta
from io import BytesIO
from unittest import mock

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from main import app

from endpoints.auth import ACCESS_TOKEN_EXPIRE_MINUTES
from handler.auth import oauth_handler
from handler.auth.constants import Scope
from handler.database import db_device_handler, db_device_save_sync_handler
from handler.redis_handler import sync_cache
from models.assets import Save
from models.device import Device
from models.platform import Platform
from models.rom import Rom
from models.user import User


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def clear_cache():
    yield
    sync_cache.flushall()


@pytest.fixture
def device(admin_user: User):
    return db_device_handler.add_device(
        Device(
            id="test-sync-device",
            user_id=admin_user.id,
            name="Sync Test Device",
        )
    )


@pytest.fixture
def token_without_device_scopes(admin_user: User):
    scopes = [
        s
        for s in admin_user.oauth_scopes
        if s not in (Scope.DEVICES_READ, Scope.DEVICES_WRITE)
    ]
    return oauth_handler.create_oauth_token(
        data={
            "sub": admin_user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(scopes),
            "type": "access",
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )


class TestSaveSyncEndpoints:
    def test_get_saves_without_device_id(self, client, access_token: str, save: Save):
        response = client.get(
            "/api/saves",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == save.id
        assert data[0]["device_syncs"] == []

    def test_get_saves_with_device_id_no_sync(
        self, client, access_token: str, save: Save, device: Device
    ):
        response = client.get(
            f"/api/saves?device_id={device.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert len(data[0]["device_syncs"]) == 1
        assert data[0]["device_syncs"][0]["device_id"] == device.id
        assert data[0]["device_syncs"][0]["is_untracked"] is False

    def test_get_saves_with_device_id_synced(
        self, client, access_token: str, save: Save, device: Device
    ):
        db_device_save_sync_handler.upsert_sync(device_id=device.id, save_id=save.id)

        response = client.get(
            f"/api/saves?device_id={device.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data[0]["device_syncs"]) == 1
        assert data[0]["device_syncs"][0]["is_untracked"] is False

    def test_get_single_save_with_device_id(
        self, client, access_token: str, save: Save, device: Device
    ):
        response = client.get(
            f"/api/saves/{save.id}?device_id={device.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == save.id
        assert len(data["device_syncs"]) == 1
        assert data["device_syncs"][0]["is_untracked"] is False

    def test_track_save(self, client, access_token: str, save: Save, device: Device):
        db_device_save_sync_handler.set_untracked(
            device_id=device.id, save_id=save.id, untracked=True
        )

        response = client.post(
            f"/api/saves/{save.id}/track",
            json={"device_id": device.id},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["device_syncs"]) == 1
        assert data["device_syncs"][0]["is_untracked"] is False

    def test_untrack_save(self, client, access_token: str, save: Save, device: Device):
        response = client.post(
            f"/api/saves/{save.id}/untrack",
            json={"device_id": device.id},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["device_syncs"]) == 1
        assert data["device_syncs"][0]["is_untracked"] is True

    def test_track_save_not_found(self, client, access_token: str, device: Device):
        response = client.post(
            "/api/saves/99999/track",
            json={"device_id": device.id},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_track_save_device_not_found(self, client, access_token: str, save: Save):
        response = client.post(
            f"/api/saves/{save.id}/track",
            json={"device_id": "nonexistent-device"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_saves_with_invalid_device_id_returns_404(
        self, client, access_token: str, save: Save
    ):
        response = client.get(
            "/api/saves?device_id=nonexistent-device",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "nonexistent-device" in response.json()["detail"]

    def test_get_saves_with_device_id_no_saves(
        self, client, access_token: str, device: Device
    ):
        """Test empty save_ids path in get_syncs_for_device_and_saves."""
        response = client.get(
            f"/api/saves?device_id={device.id}&rom_id=99999",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_untrack_save_never_synced_creates_untracked_record(
        self, client, access_token: str, save: Save, device: Device
    ):
        """Untracking a save that was never synced creates a new untracked record."""
        sync = db_device_save_sync_handler.get_sync(
            device_id=device.id, save_id=save.id
        )
        assert sync is None

        response = client.post(
            f"/api/saves/{save.id}/untrack",
            json={"device_id": device.id},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["device_syncs"]) == 1
        assert data["device_syncs"][0]["is_untracked"] is True

        sync = db_device_save_sync_handler.get_sync(
            device_id=device.id, save_id=save.id
        )
        assert sync is not None
        assert sync.is_untracked is True

    def test_track_save_never_synced_is_noop(
        self, client, access_token: str, save: Save, device: Device
    ):
        """Tracking a save that was never synced doesn't create a DB record.

        The response still includes a synthetic sync entry (is_untracked=False)
        but no actual record is created in the database.
        """
        sync = db_device_save_sync_handler.get_sync(
            device_id=device.id, save_id=save.id
        )
        assert sync is None

        response = client.post(
            f"/api/saves/{save.id}/track",
            json={"device_id": device.id},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["device_syncs"]) == 1
        assert data["device_syncs"][0]["is_untracked"] is False

        sync = db_device_save_sync_handler.get_sync(
            device_id=device.id, save_id=save.id
        )
        assert sync is None

    def test_get_single_save_with_invalid_device_id_returns_404(
        self, client, access_token: str, save: Save
    ):
        response = client.get(
            f"/api/saves/{save.id}?device_id=nonexistent-device",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "nonexistent-device" in response.json()["detail"]


class TestSaveUploadWithSync:
    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_upload_save_without_device_id(
        self,
        mock_scan,
        _mock_write,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
    ):
        mock_save = Save(
            file_name="test.sav",
            file_name_no_tags="test",
            file_name_no_ext="test",
            file_extension="sav",
            file_path=f"{platform.slug}/saves",
            file_size_bytes=100,
            rom_id=rom.id,
            user_id=admin_user.id,
        )
        mock_scan.return_value = mock_save

        file_content = BytesIO(b"test save data")
        response = client.post(
            f"/api/saves?rom_id={rom.id}",
            files={"saveFile": ("test.sav", file_content, "application/octet-stream")},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["device_syncs"] == []

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_upload_save_with_device_id(
        self,
        mock_scan,
        _mock_write,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
        device: Device,
    ):
        mock_save = Save(
            file_name="test.sav",
            file_name_no_tags="test",
            file_name_no_ext="test",
            file_extension="sav",
            file_path=f"{platform.slug}/saves",
            file_size_bytes=100,
            rom_id=rom.id,
            user_id=admin_user.id,
        )
        mock_scan.return_value = mock_save

        file_content = BytesIO(b"test save data")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&device_id={device.id}",
            files={"saveFile": ("test.sav", file_content, "application/octet-stream")},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["device_syncs"]) == 1
        assert data["device_syncs"][0]["device_id"] == device.id
        assert data["device_syncs"][0]["is_untracked"] is False

    def test_upload_save_with_invalid_device_id_returns_404(
        self,
        client,
        access_token: str,
        rom: Rom,
    ):
        file_content = BytesIO(b"test save data")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&device_id=nonexistent-device",
            files={"saveFile": ("test.sav", file_content, "application/octet-stream")},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "nonexistent-device" in response.json()["detail"]

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_upload_save_with_save_name(
        self,
        mock_scan,
        _mock_write,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
    ):
        mock_save = Save(
            file_name="slot1.sav",
            file_name_no_tags="slot1",
            file_name_no_ext="slot1",
            file_extension="sav",
            file_path=f"{platform.slug}/saves",
            file_size_bytes=100,
            rom_id=rom.id,
            user_id=admin_user.id,
        )
        mock_scan.return_value = mock_save

        file_content = BytesIO(b"test save data")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&save_name=Slot%201",
            files={"saveFile": ("slot1.sav", file_content, "application/octet-stream")},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["save_name"] == "Slot 1"


class TestSaveConflictDetection:
    @pytest.fixture
    def device_b(self, admin_user: User):
        return db_device_handler.add_device(
            Device(
                id="test-sync-device-b",
                user_id=admin_user.id,
                name="Device B",
            )
        )

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_first_upload_from_device_no_sync_exists(
        self,
        mock_scan,
        _mock_write,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
        save: Save,
        device: Device,
    ):
        """Scenario 1: First upload from device (no sync record exists) should succeed."""
        mock_scan.return_value = save

        file_content = BytesIO(b"save data from device")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&device_id={device.id}",
            files={
                "saveFile": (save.file_name, file_content, "application/octet-stream")
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["device_syncs"]) == 1
        assert data["device_syncs"][0]["device_id"] == device.id

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_sync_equals_updated_at_no_conflict(
        self,
        mock_scan,
        _mock_write,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
        save: Save,
        device: Device,
    ):
        """Scenario 2: Device sync timestamp equals save.updated_at should succeed."""
        db_device_save_sync_handler.upsert_sync(
            device_id=device.id, save_id=save.id, synced_at=save.updated_at
        )

        mock_scan.return_value = save

        file_content = BytesIO(b"updated save data")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&device_id={device.id}",
            files={
                "saveFile": (save.file_name, file_content, "application/octet-stream")
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_upload_without_device_id_always_succeeds(
        self,
        mock_scan,
        _mock_write,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
        save: Save,
    ):
        """Scenario 3: Upload without device_id bypasses conflict detection."""
        mock_scan.return_value = save

        file_content = BytesIO(b"updated from web ui")
        response = client.post(
            f"/api/saves?rom_id={rom.id}",
            files={
                "saveFile": (save.file_name, file_content, "application/octet-stream")
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["device_syncs"] == []

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_new_save_with_device_id_succeeds(
        self,
        mock_scan,
        _mock_write,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
        device: Device,
    ):
        """Scenario 4: Creating a new save with device_id always succeeds."""
        new_save = Save(
            file_name="brand_new_save.sav",
            file_name_no_tags="brand_new_save",
            file_name_no_ext="brand_new_save",
            file_extension="sav",
            file_path=f"{platform.slug}/saves",
            file_size_bytes=100,
            rom_id=rom.id,
            user_id=admin_user.id,
        )
        mock_scan.return_value = new_save

        file_content = BytesIO(b"brand new save data")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&device_id={device.id}",
            files={
                "saveFile": (
                    "brand_new_save.sav",
                    file_content,
                    "application/octet-stream",
                )
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["device_syncs"]) == 1

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_device_b_downloads_then_uploads_no_conflict(
        self,
        mock_scan,
        _mock_write,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
        save: Save,
        device: Device,
        device_b: Device,
    ):
        """Scenario 5: Device A uploads, Device B downloads (syncs), Device B uploads.

        Device B should succeed because it has the latest sync timestamp.
        """

        db_device_save_sync_handler.upsert_sync(
            device_id=device.id, save_id=save.id, synced_at=save.updated_at
        )

        db_device_save_sync_handler.upsert_sync(
            device_id=device_b.id, save_id=save.id, synced_at=save.updated_at
        )

        mock_scan.return_value = save

        file_content = BytesIO(b"save from device b after download")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&device_id={device_b.id}",
            files={
                "saveFile": (save.file_name, file_content, "application/octet-stream")
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["device_syncs"][0]["device_id"] == device_b.id

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_device_b_uploads_without_download_conflict(
        self,
        mock_scan,
        _mock_write,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
        save: Save,
        device: Device,
        device_b: Device,
    ):
        """Scenario 6: Device A uploads, Device B uploads without downloading first.

        Device B has an old sync from before Device A's upload, so conflict.
        """
        from datetime import datetime, timedelta, timezone

        old_sync_time = datetime.now(timezone.utc) - timedelta(hours=2)
        db_device_save_sync_handler.upsert_sync(
            device_id=device_b.id, save_id=save.id, synced_at=old_sync_time
        )

        db_device_save_sync_handler.upsert_sync(
            device_id=device.id, save_id=save.id, synced_at=save.updated_at
        )

        mock_scan.return_value = save

        file_content = BytesIO(b"stale save from device b")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&device_id={device_b.id}",
            files={
                "saveFile": (save.file_name, file_content, "application/octet-stream")
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()
        assert data["detail"]["error"] == "conflict"
        assert "device_sync_time" in data["detail"]

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_web_ui_uploads_then_device_with_old_sync_conflict(
        self,
        mock_scan,
        _mock_write,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
        save: Save,
        device: Device,
    ):
        """Scenario 7: Web UI uploads (no device_id), device with old sync uploads.

        Device A synced the save, then web UI uploaded a new version (without device_id).
        Device A tries to upload without re-downloading - should conflict.
        """
        from datetime import datetime, timedelta, timezone

        old_sync_time = datetime.now(timezone.utc) - timedelta(hours=1)
        db_device_save_sync_handler.upsert_sync(
            device_id=device.id, save_id=save.id, synced_at=old_sync_time
        )

        mock_scan.return_value = save

        file_content = BytesIO(b"stale save from device after web update")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&device_id={device.id}",
            files={
                "saveFile": (save.file_name, file_content, "application/octet-stream")
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()
        assert data["detail"]["error"] == "conflict"

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_upload_conflict_bypassed_with_overwrite(
        self,
        mock_scan,
        _mock_write,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
        save: Save,
        device: Device,
    ):
        """Verify overwrite=true bypasses conflict detection."""
        from datetime import datetime, timedelta, timezone

        old_sync_time = datetime.now(timezone.utc) - timedelta(hours=1)
        db_device_save_sync_handler.upsert_sync(
            device_id=device.id, save_id=save.id, synced_at=old_sync_time
        )

        mock_scan.return_value = save

        file_content = BytesIO(b"forced overwrite")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&device_id={device.id}&overwrite=true",
            files={
                "saveFile": (save.file_name, file_content, "application/octet-stream")
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_conflict_response_contains_details(
        self,
        mock_scan,
        _mock_write,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
        save: Save,
        device: Device,
    ):
        """Verify conflict response contains all necessary details for client handling."""
        from datetime import datetime, timedelta, timezone

        old_sync_time = datetime.now(timezone.utc) - timedelta(hours=1)
        db_device_save_sync_handler.upsert_sync(
            device_id=device.id, save_id=save.id, synced_at=old_sync_time
        )

        mock_scan.return_value = save

        file_content = BytesIO(b"conflicting save")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&device_id={device.id}",
            files={
                "saveFile": (save.file_name, file_content, "application/octet-stream")
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()
        detail = data["detail"]

        assert detail["error"] == "conflict"
        assert "message" in detail
        assert "save_id" in detail
        assert detail["save_id"] == save.id
        assert "current_save_time" in detail
        assert "device_sync_time" in detail


class TestDeviceScopeEnforcement:
    def test_get_saves_with_device_id_requires_scope(
        self, client, token_without_device_scopes: str, save: Save, device: Device
    ):
        response = client.get(
            f"/api/saves?device_id={device.id}",
            headers={"Authorization": f"Bearer {token_without_device_scopes}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_single_save_with_device_id_requires_scope(
        self, client, token_without_device_scopes: str, save: Save, device: Device
    ):
        response = client.get(
            f"/api/saves/{save.id}?device_id={device.id}",
            headers={"Authorization": f"Bearer {token_without_device_scopes}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_upload_save_with_device_id_requires_scope(
        self,
        mock_scan,
        _mock_write,
        client,
        token_without_device_scopes: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
        device: Device,
    ):
        mock_save = Save(
            file_name="test.sav",
            file_name_no_tags="test",
            file_name_no_ext="test",
            file_extension="sav",
            file_path=f"{platform.slug}/saves",
            file_size_bytes=100,
            rom_id=rom.id,
            user_id=admin_user.id,
        )
        mock_scan.return_value = mock_save

        file_content = BytesIO(b"test save data")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&device_id={device.id}",
            files={"saveFile": ("test.sav", file_content, "application/octet-stream")},
            headers={"Authorization": f"Bearer {token_without_device_scopes}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_track_save_requires_scope(
        self, client, token_without_device_scopes: str, save: Save, device: Device
    ):
        response = client.post(
            f"/api/saves/{save.id}/track",
            json={"device_id": device.id},
            headers={"Authorization": f"Bearer {token_without_device_scopes}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_untrack_save_requires_scope(
        self, client, token_without_device_scopes: str, save: Save, device: Device
    ):
        response = client.post(
            f"/api/saves/{save.id}/untrack",
            json={"device_id": device.id},
            headers={"Authorization": f"Bearer {token_without_device_scopes}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
