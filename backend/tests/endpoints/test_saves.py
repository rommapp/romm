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
        assert data[0]["device_syncs"][0]["is_current"] is False

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
        assert data[0]["device_syncs"][0]["is_current"] is True

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
    def test_upload_save_with_slot(
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
            slot="Slot 1",
        )
        mock_scan.return_value = mock_save

        file_content = BytesIO(b"test save data")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&slot=Slot%201",
            files={"saveFile": ("slot1.sav", file_content, "application/octet-stream")},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["slot"] == "Slot 1"


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
        assert "since your last sync" in data["detail"]

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
        assert "since your last sync" in data["detail"]

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
        assert "since your last sync" in data["detail"]

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_out_of_sync_response_with_slot(
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
        """Verify out_of_sync response when uploading with slot (non-destructive).

        Slot conflict detection checks if device has synced the latest save in the slot,
        not by exact filename (since datetime tags make each upload unique).
        """
        from datetime import datetime, timedelta, timezone

        from handler.database import db_save_handler

        existing_slot_save = Save(
            file_name="existing_slot_save.sav",
            file_name_no_tags="existing_slot_save",
            file_name_no_ext="existing_slot_save",
            file_extension="sav",
            file_path=f"{platform.slug}/saves",
            file_size_bytes=100,
            rom_id=rom.id,
            user_id=admin_user.id,
            slot="TestSlot",
        )
        db_slot_save = db_save_handler.add_save(existing_slot_save)

        old_sync_time = datetime.now(timezone.utc) - timedelta(hours=1)
        db_device_save_sync_handler.upsert_sync(
            device_id=device.id, save_id=db_slot_save.id, synced_at=old_sync_time
        )

        mock_scan.return_value = Save(
            file_name="new_upload.sav",
            file_name_no_tags="new_upload",
            file_name_no_ext="new_upload",
            file_extension="sav",
            file_path=f"{platform.slug}/saves",
            file_size_bytes=100,
            rom_id=rom.id,
            user_id=admin_user.id,
            slot="TestSlot",
        )

        file_content = BytesIO(b"out of sync save")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&device_id={device.id}&slot=TestSlot",
            files={
                "saveFile": ("new_upload.sav", file_content, "application/octet-stream")
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()
        assert "newer save since your last sync" in data["detail"]

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_first_upload_to_slot_succeeds(
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
        """First upload to a slot (no existing saves) should succeed."""
        mock_scan.return_value = Save(
            file_name="first_in_slot.sav",
            file_name_no_tags="first_in_slot",
            file_name_no_ext="first_in_slot",
            file_extension="sav",
            file_path=f"{platform.slug}/saves",
            file_size_bytes=100,
            rom_id=rom.id,
            user_id=admin_user.id,
            slot="BrandNewSlot",
        )

        file_content = BytesIO(b"first save in slot")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&device_id={device.id}&slot=BrandNewSlot",
            files={
                "saveFile": (
                    "first_in_slot.sav",
                    file_content,
                    "application/octet-stream",
                )
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["slot"] == "BrandNewSlot"

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_upload_to_slot_with_current_sync_succeeds(
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
        """Upload to slot succeeds when device has synced the latest save."""
        from handler.database import db_save_handler

        existing_slot_save = Save(
            file_name="synced_save.sav",
            file_name_no_tags="synced_save",
            file_name_no_ext="synced_save",
            file_extension="sav",
            file_path=f"{platform.slug}/saves",
            file_size_bytes=100,
            rom_id=rom.id,
            user_id=admin_user.id,
            slot="SyncedSlot",
        )
        db_slot_save = db_save_handler.add_save(existing_slot_save)

        db_device_save_sync_handler.upsert_sync(
            device_id=device.id,
            save_id=db_slot_save.id,
            synced_at=db_slot_save.updated_at,
        )

        mock_scan.return_value = Save(
            file_name="next_upload.sav",
            file_name_no_tags="next_upload",
            file_name_no_ext="next_upload",
            file_extension="sav",
            file_path=f"{platform.slug}/saves",
            file_size_bytes=100,
            rom_id=rom.id,
            user_id=admin_user.id,
            slot="SyncedSlot",
        )

        file_content = BytesIO(b"next save in slot")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&device_id={device.id}&slot=SyncedSlot",
            files={
                "saveFile": (
                    "next_upload.sav",
                    file_content,
                    "application/octet-stream",
                )
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_out_of_sync_with_no_prior_device_sync(
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
        """Device that never synced any save in slot should get out_of_sync."""
        from handler.database import db_save_handler

        existing_slot_save = Save(
            file_name="never_synced.sav",
            file_name_no_tags="never_synced",
            file_name_no_ext="never_synced",
            file_extension="sav",
            file_path=f"{platform.slug}/saves",
            file_size_bytes=100,
            rom_id=rom.id,
            user_id=admin_user.id,
            slot="NeverSyncedSlot",
        )
        db_save_handler.add_save(existing_slot_save)

        mock_scan.return_value = Save(
            file_name="upload_attempt.sav",
            file_name_no_tags="upload_attempt",
            file_name_no_ext="upload_attempt",
            file_extension="sav",
            file_path=f"{platform.slug}/saves",
            file_size_bytes=100,
            rom_id=rom.id,
            user_id=admin_user.id,
            slot="NeverSyncedSlot",
        )

        file_content = BytesIO(b"upload without prior sync")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&device_id={device.id}&slot=NeverSyncedSlot",
            files={
                "saveFile": (
                    "upload_attempt.sav",
                    file_content,
                    "application/octet-stream",
                )
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()
        assert "newer save since your last sync" in data["detail"]


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


class TestSlotFiltering:
    @pytest.fixture
    def saves_with_slots(
        self, admin_user: User, rom: Rom, platform: Platform
    ) -> list[Save]:
        from handler.database import db_save_handler

        saves = []
        for i, slot in enumerate([None, "Slot 1", "Slot 1", "Slot 2"]):
            save = Save(
                file_name=f"save_{i}.sav",
                file_name_no_tags=f"save_{i}",
                file_name_no_ext=f"save_{i}",
                file_extension="sav",
                file_path=f"{platform.slug}/saves",
                file_size_bytes=100 + i,
                rom_id=rom.id,
                user_id=admin_user.id,
                slot=slot,
            )
            saves.append(db_save_handler.add_save(save))
        return saves

    def test_get_saves_without_slot_filter(
        self, client, access_token: str, saves_with_slots: list[Save]
    ):
        response = client.get(
            "/api/saves",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 4
        for item in data:
            assert "slot" in item
            assert "id" in item
            assert "rom_id" in item

    def test_get_saves_with_slot_filter(
        self, client, access_token: str, rom: Rom, saves_with_slots: list[Save]
    ):
        response = client.get(
            f"/api/saves?rom_id={rom.id}&slot=Slot%201",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        for item in data:
            assert item["slot"] == "Slot 1"

    def test_get_saves_with_nonexistent_slot(
        self, client, access_token: str, rom: Rom, saves_with_slots: list[Save]
    ):
        response = client.get(
            f"/api/saves?rom_id={rom.id}&slot=NonexistentSlot",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 0


class TestDatetimeTagging:
    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_upload_with_slot_applies_datetime_tag(
        self,
        mock_scan,
        mock_write,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
    ):
        import re

        mock_save = Save(
            file_name="test [2026-01-31_12-00-00].sav",
            file_name_no_tags="test",
            file_name_no_ext="test [2026-01-31_12-00-00]",
            file_extension="sav",
            file_path=f"{platform.slug}/saves",
            file_size_bytes=100,
            rom_id=rom.id,
            user_id=admin_user.id,
            slot="main",
        )
        mock_scan.return_value = mock_save

        file_content = BytesIO(b"test save data")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&slot=main",
            files={"saveFile": ("test.sav", file_content, "application/octet-stream")},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        mock_write.assert_called_once()
        call_args = mock_write.call_args
        written_filename = call_args[1].get("filename") or call_args[0][2]
        assert re.search(r" \[\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\]", written_filename)

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_upload_without_slot_no_datetime_tag(
        self,
        mock_scan,
        mock_write,
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
        mock_write.assert_called_once()
        call_args = mock_write.call_args
        written_filename = call_args[1].get("filename") or call_args[0][2]
        assert written_filename == "test.sav"

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_upload_with_existing_datetime_tag_replaces_it(
        self,
        mock_scan,
        mock_write,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
    ):
        import re

        mock_save = Save(
            file_name="test [2026-01-31_12-00-00].sav",
            file_name_no_tags="test",
            file_name_no_ext="test [2026-01-31_12-00-00]",
            file_extension="sav",
            file_path=f"{platform.slug}/saves",
            file_size_bytes=100,
            rom_id=rom.id,
            user_id=admin_user.id,
            slot="main",
        )
        mock_scan.return_value = mock_save

        file_content = BytesIO(b"test save data")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&slot=main",
            files={
                "saveFile": (
                    "test [2020-01-01_00-00-00].sav",
                    file_content,
                    "application/octet-stream",
                )
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        mock_write.assert_called_once()
        call_args = mock_write.call_args
        written_filename = call_args[1].get("filename") or call_args[0][2]
        datetime_matches = re.findall(
            r"\[\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\]", written_filename
        )
        assert len(datetime_matches) == 1
        assert "2020-01-01" not in written_filename


class TestAutocleanup:
    @pytest.fixture
    def slot_saves(self, admin_user: User, rom: Rom, platform: Platform) -> list[Save]:
        from datetime import datetime, timedelta, timezone

        from handler.database import db_save_handler

        saves = []
        base_time = datetime.now(timezone.utc) - timedelta(hours=20)
        for i in range(15):
            save = Save(
                file_name=f"autosave_{i}.sav",
                file_name_no_tags=f"autosave_{i}",
                file_name_no_ext=f"autosave_{i}",
                file_extension="sav",
                file_path=f"{platform.slug}/saves",
                file_size_bytes=100 + i,
                rom_id=rom.id,
                user_id=admin_user.id,
                slot="autosave",
            )
            created = db_save_handler.add_save(save)
            db_save_handler.update_save(
                created.id, {"updated_at": base_time + timedelta(hours=i)}
            )
            saves.append(created)
        return saves

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch(
        "endpoints.saves.fs_asset_handler.remove_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_autocleanup_deletes_old_saves(
        self,
        mock_scan,
        mock_remove,
        mock_write,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
        slot_saves: list[Save],
    ):
        from handler.database import db_save_handler

        initial_saves = db_save_handler.get_saves(
            user_id=admin_user.id, rom_id=rom.id, slot="autosave"
        )
        assert len(initial_saves) == 15

        mock_save = Save(
            file_name="new_autosave.sav",
            file_name_no_tags="new_autosave",
            file_name_no_ext="new_autosave",
            file_extension="sav",
            file_path=f"{platform.slug}/saves",
            file_size_bytes=100,
            rom_id=rom.id,
            user_id=admin_user.id,
            slot="autosave",
        )
        mock_scan.return_value = mock_save

        file_content = BytesIO(b"new save")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&slot=autosave&autocleanup=true&autocleanup_limit=10",
            files={
                "saveFile": (
                    "new_autosave.sav",
                    file_content,
                    "application/octet-stream",
                )
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert mock_remove.call_count == 6

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch(
        "endpoints.saves.fs_asset_handler.remove_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_autocleanup_disabled_by_default(
        self,
        mock_scan,
        mock_remove,
        mock_write,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
        slot_saves: list[Save],
    ):
        mock_save = Save(
            file_name="new_save.sav",
            file_name_no_tags="new_save",
            file_name_no_ext="new_save",
            file_extension="sav",
            file_path=f"{platform.slug}/saves",
            file_size_bytes=100,
            rom_id=rom.id,
            user_id=admin_user.id,
            slot="autosave",
        )
        mock_scan.return_value = mock_save

        file_content = BytesIO(b"new save")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&slot=autosave",
            files={
                "saveFile": ("new_save.sav", file_content, "application/octet-stream")
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        mock_remove.assert_not_called()

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch(
        "endpoints.saves.fs_asset_handler.remove_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_autocleanup_without_slot_does_nothing(
        self,
        mock_scan,
        mock_remove,
        mock_write,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
    ):
        mock_save = Save(
            file_name="noslotsave.sav",
            file_name_no_tags="noslotsave",
            file_name_no_ext="noslotsave",
            file_extension="sav",
            file_path=f"{platform.slug}/saves",
            file_size_bytes=100,
            rom_id=rom.id,
            user_id=admin_user.id,
        )
        mock_scan.return_value = mock_save

        file_content = BytesIO(b"no slot save")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&autocleanup=true&autocleanup_limit=5",
            files={
                "saveFile": ("noslotsave.sav", file_content, "application/octet-stream")
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        mock_remove.assert_not_called()


class TestSavesSummaryEndpoint:
    @pytest.fixture
    def summary_saves(
        self, admin_user: User, rom: Rom, platform: Platform
    ) -> list[Save]:
        from datetime import datetime, timedelta, timezone

        from handler.database import db_save_handler

        saves = []
        base_time = datetime.now(timezone.utc) - timedelta(hours=10)

        configs = [
            (None, 0),
            (None, 1),
            (None, 2),
            ("Slot A", 3),
            ("Slot A", 4),
            ("Slot B", 5),
        ]

        for slot, offset in configs:
            save = Save(
                file_name=f"summary_save_{offset}.sav",
                file_name_no_tags=f"summary_save_{offset}",
                file_name_no_ext=f"summary_save_{offset}",
                file_extension="sav",
                file_path=f"{platform.slug}/saves",
                file_size_bytes=100 + offset,
                rom_id=rom.id,
                user_id=admin_user.id,
                slot=slot,
            )
            created = db_save_handler.add_save(save)
            db_save_handler.update_save(
                created.id, {"updated_at": base_time + timedelta(hours=offset)}
            )
            saves.append(created)
        return saves

    def test_get_saves_summary(
        self, client, access_token: str, rom: Rom, summary_saves: list[Save]
    ):
        response = client.get(
            f"/api/saves/summary?rom_id={rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "total_count" in data
        assert "slots" in data
        assert data["total_count"] == 6
        assert isinstance(data["slots"], list)
        assert len(data["slots"]) == 3

        slot_map = {s["slot"]: s for s in data["slots"]}
        assert None in slot_map or "null" in str(slot_map.keys())
        assert "Slot A" in slot_map
        assert "Slot B" in slot_map

    def test_get_saves_summary_validates_response_schema(
        self, client, access_token: str, rom: Rom, summary_saves: list[Save]
    ):
        response = client.get(
            f"/api/saves/summary?rom_id={rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert isinstance(data["total_count"], int)
        assert isinstance(data["slots"], list)

        for slot_info in data["slots"]:
            assert "slot" in slot_info
            assert "count" in slot_info
            assert "latest" in slot_info

            assert isinstance(slot_info["count"], int)
            assert slot_info["count"] > 0

            latest = slot_info["latest"]
            assert "id" in latest
            assert "rom_id" in latest
            assert "user_id" in latest
            assert "file_name" in latest
            assert "created_at" in latest
            assert "updated_at" in latest

    def test_get_saves_summary_latest_is_most_recent(
        self, client, access_token: str, rom: Rom, summary_saves: list[Save]
    ):
        response = client.get(
            f"/api/saves/summary?rom_id={rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        slot_a_info = next((s for s in data["slots"] if s["slot"] == "Slot A"), None)
        assert slot_a_info is not None
        assert slot_a_info["count"] == 2
        assert "summary_save_4" in slot_a_info["latest"]["file_name"]

    def test_get_saves_summary_requires_rom_id(self, client, access_token: str):
        response = client.get(
            "/api/saves/summary",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert "detail" in data
        assert any("rom_id" in str(err).lower() for err in data["detail"])

    def test_get_saves_summary_empty_rom(self, client, access_token: str):
        response = client.get(
            "/api/saves/summary?rom_id=999999",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_count"] == 0
        assert data["slots"] == []

    def test_get_saves_summary_requires_auth(self, client, rom: Rom):
        response = client.get(f"/api/saves/summary?rom_id={rom.id}")

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestSaveDownload:
    @mock.patch("endpoints.saves.fs_asset_handler.validate_path")
    def test_download_save_without_device_returns_file(
        self,
        mock_validate_path,
        client,
        access_token: str,
        save: Save,
        tmp_path,
    ):
        test_file = tmp_path / "test.sav"
        test_file.write_bytes(b"save file content")
        mock_validate_path.return_value = test_file

        response = client.get(
            f"/api/saves/{save.id}/content",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.content == b"save file content"

        sync = db_device_save_sync_handler.get_sync(device_id="any", save_id=save.id)
        assert sync is None

    @mock.patch("endpoints.saves.fs_asset_handler.validate_path")
    def test_download_save_with_device_returns_file(
        self,
        mock_validate_path,
        client,
        access_token: str,
        save: Save,
        device: Device,
        tmp_path,
    ):
        test_file = tmp_path / "test.sav"
        test_file.write_bytes(b"save file content")
        mock_validate_path.return_value = test_file

        response = client.get(
            f"/api/saves/{save.id}/content?device_id={device.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.content == b"save file content"

    def test_download_save_not_found(self, client, access_token: str):
        response = client.get(
            "/api/saves/99999/content",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "99999" in response.json()["detail"]

    @mock.patch("endpoints.saves.fs_asset_handler.validate_path")
    def test_download_save_file_missing_on_disk(
        self,
        mock_validate_path,
        client,
        access_token: str,
        save: Save,
        tmp_path,
    ):
        missing_file = tmp_path / "nonexistent.sav"
        mock_validate_path.return_value = missing_file

        response = client.get(
            f"/api/saves/{save.id}/content",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found on disk" in response.json()["detail"]

    @mock.patch("endpoints.saves.fs_asset_handler.validate_path")
    def test_download_save_validate_path_raises(
        self,
        mock_validate_path,
        client,
        access_token: str,
        save: Save,
    ):
        mock_validate_path.side_effect = ValueError("Invalid path")

        response = client.get(
            f"/api/saves/{save.id}/content",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    @mock.patch("endpoints.saves.fs_asset_handler.validate_path")
    def test_download_with_device_id_optimistic_true_updates_sync(
        self,
        mock_validate_path,
        client,
        access_token: str,
        save: Save,
        device: Device,
        tmp_path,
    ):
        test_file = tmp_path / "test.sav"
        test_file.write_bytes(b"save content")
        mock_validate_path.return_value = test_file

        sync_before = db_device_save_sync_handler.get_sync(
            device_id=device.id, save_id=save.id
        )
        assert sync_before is None

        response = client.get(
            f"/api/saves/{save.id}/content?device_id={device.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK

        sync_after = db_device_save_sync_handler.get_sync(
            device_id=device.id, save_id=save.id
        )
        assert sync_after is not None
        assert sync_after.last_synced_at.replace(
            microsecond=0, tzinfo=None
        ) == save.updated_at.replace(microsecond=0, tzinfo=None)

    @mock.patch("endpoints.saves.fs_asset_handler.validate_path")
    def test_download_with_device_id_optimistic_false_no_sync_update(
        self,
        mock_validate_path,
        client,
        access_token: str,
        save: Save,
        device: Device,
        tmp_path,
    ):
        test_file = tmp_path / "test.sav"
        test_file.write_bytes(b"save content")
        mock_validate_path.return_value = test_file

        response = client.get(
            f"/api/saves/{save.id}/content?device_id={device.id}&optimistic=false",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK

        sync = db_device_save_sync_handler.get_sync(
            device_id=device.id, save_id=save.id
        )
        assert sync is None

    @mock.patch("endpoints.saves.fs_asset_handler.validate_path")
    def test_download_with_invalid_device_id_returns_404(
        self,
        mock_validate_path,
        client,
        access_token: str,
        save: Save,
        tmp_path,
    ):
        test_file = tmp_path / "test.sav"
        test_file.write_bytes(b"save content")
        mock_validate_path.return_value = test_file

        response = client.get(
            f"/api/saves/{save.id}/content?device_id=nonexistent-device",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "nonexistent-device" in response.json()["detail"]

    @mock.patch("endpoints.saves.fs_asset_handler.validate_path")
    def test_download_without_device_scope_forbidden(
        self,
        mock_validate_path,
        client,
        token_without_device_scopes: str,
        save: Save,
        device: Device,
        tmp_path,
    ):
        test_file = tmp_path / "test.sav"
        test_file.write_bytes(b"save content")
        mock_validate_path.return_value = test_file

        response = client.get(
            f"/api/saves/{save.id}/content?device_id={device.id}",
            headers={"Authorization": f"Bearer {token_without_device_scopes}"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestConfirmDownload:
    def test_confirm_download_creates_sync_record(
        self,
        client,
        access_token: str,
        save: Save,
        device: Device,
    ):
        sync_before = db_device_save_sync_handler.get_sync(
            device_id=device.id, save_id=save.id
        )
        assert sync_before is None

        response = client.post(
            f"/api/saves/{save.id}/downloaded",
            json={"device_id": device.id},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["device_syncs"]) == 1
        assert data["device_syncs"][0]["device_id"] == device.id

        sync_after = db_device_save_sync_handler.get_sync(
            device_id=device.id, save_id=save.id
        )
        assert sync_after is not None
        assert sync_after.last_synced_at.replace(
            microsecond=0, tzinfo=None
        ) == save.updated_at.replace(microsecond=0, tzinfo=None)

    def test_confirm_download_updates_existing_sync(
        self,
        client,
        access_token: str,
        save: Save,
        device: Device,
    ):
        from datetime import datetime, timedelta, timezone

        old_sync_time = datetime.now(timezone.utc) - timedelta(hours=5)
        db_device_save_sync_handler.upsert_sync(
            device_id=device.id, save_id=save.id, synced_at=old_sync_time
        )

        response = client.post(
            f"/api/saves/{save.id}/downloaded",
            json={"device_id": device.id},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK

        sync = db_device_save_sync_handler.get_sync(
            device_id=device.id, save_id=save.id
        )
        assert sync.last_synced_at.replace(
            microsecond=0, tzinfo=None
        ) == save.updated_at.replace(microsecond=0, tzinfo=None)
        assert sync.last_synced_at.replace(
            microsecond=0, tzinfo=None
        ) != old_sync_time.replace(microsecond=0, tzinfo=None)

    def test_confirm_download_updates_device_last_seen(
        self,
        client,
        access_token: str,
        save: Save,
        device: Device,
    ):
        original_last_seen = device.last_seen

        response = client.post(
            f"/api/saves/{save.id}/downloaded",
            json={"device_id": device.id},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK

        updated_device = db_device_handler.get_device(
            device_id=device.id, user_id=device.user_id
        )
        if original_last_seen:
            assert updated_device.last_seen > original_last_seen
        else:
            assert updated_device.last_seen is not None

    def test_confirm_download_save_not_found(
        self,
        client,
        access_token: str,
        device: Device,
    ):
        response = client.post(
            "/api/saves/99999/downloaded",
            json={"device_id": device.id},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "99999" in response.json()["detail"]

    def test_confirm_download_device_not_found(
        self,
        client,
        access_token: str,
        save: Save,
    ):
        response = client.post(
            f"/api/saves/{save.id}/downloaded",
            json={"device_id": "nonexistent-device"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "nonexistent-device" in response.json()["detail"]


class TestContentHashDeduplication:
    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save")
    def test_slot_upload_includes_content_hash(
        self,
        mock_scan_save,
        mock_write_file,
        client,
        access_token: str,
        rom: Rom,
    ):
        from models.assets import Save as SaveModel

        mock_save = SaveModel(
            id=999,
            file_name="test [2026-01-31_12-00-00].sav",
            file_name_no_tags="test.sav",
            file_name_no_ext="test [2026-01-31_12-00-00]",
            file_extension="sav",
            file_path="/saves/path",
            file_size_bytes=1024,
            content_hash="abc123def456789012345678901234ab",
            rom_id=rom.id,
            user_id=1,
        )
        mock_scan_save.return_value = mock_save

        response = client.post(
            "/api/saves",
            params={"rom_id": rom.id, "slot": "Slot1"},
            files={
                "saveFile": (
                    "test.sav",
                    BytesIO(b"save content"),
                    "application/octet-stream",
                )
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "content_hash" in data
        assert data["content_hash"] == "abc123def456789012345678901234ab"

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch(
        "endpoints.saves.fs_asset_handler.remove_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save")
    def test_duplicate_hash_returns_existing_save(
        self,
        mock_scan_save,
        mock_remove_file,
        mock_write_file,
        client,
        access_token: str,
        rom: Rom,
        save: Save,
    ):
        from handler.database import db_save_handler

        db_save_handler.update_save(
            save.id, {"content_hash": "duplicate_hash_12345678901234"}
        )

        from models.assets import Save as SaveModel

        mock_save = SaveModel(
            id=None,
            file_name="new [2026-01-31_12-00-00].sav",
            file_name_no_tags="new.sav",
            file_name_no_ext="new [2026-01-31_12-00-00]",
            file_extension="sav",
            file_path="/saves/path",
            file_size_bytes=1024,
            content_hash="duplicate_hash_12345678901234",
            rom_id=rom.id,
            user_id=1,
        )
        mock_scan_save.return_value = mock_save

        response = client.post(
            "/api/saves",
            params={"rom_id": rom.id, "slot": "Slot1"},
            files={
                "saveFile": (
                    "new.sav",
                    BytesIO(b"save content"),
                    "application/octet-stream",
                )
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == save.id
        assert data["content_hash"] == "duplicate_hash_12345678901234"
        mock_remove_file.assert_called_once()

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save")
    def test_duplicate_hash_with_overwrite_succeeds(
        self,
        mock_scan_save,
        mock_write_file,
        client,
        access_token: str,
        rom: Rom,
        save: Save,
    ):
        from handler.database import db_save_handler

        db_save_handler.update_save(
            save.id, {"content_hash": "duplicate_hash_12345678901234"}
        )

        from models.assets import Save as SaveModel

        mock_save = SaveModel(
            id=None,
            file_name="new [2026-01-31_12-00-00].sav",
            file_name_no_tags="new.sav",
            file_name_no_ext="new [2026-01-31_12-00-00]",
            file_extension="sav",
            file_path="/saves/path",
            file_size_bytes=1024,
            content_hash="duplicate_hash_12345678901234",
            rom_id=rom.id,
            user_id=1,
        )
        mock_scan_save.return_value = mock_save

        response = client.post(
            "/api/saves",
            params={"rom_id": rom.id, "slot": "Slot1", "overwrite": True},
            files={
                "saveFile": (
                    "new.sav",
                    BytesIO(b"save content"),
                    "application/octet-stream",
                )
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save")
    def test_non_slot_upload_no_dedup_block(
        self,
        mock_scan_save,
        mock_write_file,
        client,
        access_token: str,
        rom: Rom,
        save: Save,
    ):
        from handler.database import db_save_handler

        db_save_handler.update_save(
            save.id, {"content_hash": "duplicate_hash_12345678901234"}
        )

        from models.assets import Save as SaveModel

        mock_save = SaveModel(
            id=None,
            file_name="new.sav",
            file_name_no_tags="new.sav",
            file_name_no_ext="new",
            file_extension="sav",
            file_path="/saves/path",
            file_size_bytes=1024,
            content_hash="duplicate_hash_12345678901234",
            rom_id=rom.id,
            user_id=1,
        )
        mock_scan_save.return_value = mock_save

        response = client.post(
            "/api/saves",
            params={"rom_id": rom.id},
            files={
                "saveFile": (
                    "new.sav",
                    BytesIO(b"save content"),
                    "application/octet-stream",
                )
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK


class TestContentHashComputation:
    def test_compute_file_hash(self, tmp_path):
        from handler.scan_handler import _compute_file_hash

        test_file = tmp_path / "test.sav"
        test_file.write_bytes(b"test content for hashing")

        hash_result = _compute_file_hash(str(test_file))

        assert hash_result is not None
        assert len(hash_result) == 32

        hash_result2 = _compute_file_hash(str(test_file))
        assert hash_result == hash_result2

    def test_same_content_produces_same_hash(self, tmp_path):
        from handler.scan_handler import _compute_file_hash

        file1 = tmp_path / "save1.sav"
        file2 = tmp_path / "save2.sav"
        file1.write_bytes(b"identical content")
        file2.write_bytes(b"identical content")

        hash1 = _compute_file_hash(str(file1))
        hash2 = _compute_file_hash(str(file2))

        assert hash1 == hash2

    def test_different_content_produces_different_hash(self, tmp_path):
        from handler.scan_handler import _compute_file_hash

        file1 = tmp_path / "save1.sav"
        file2 = tmp_path / "save2.sav"
        file1.write_bytes(b"content A")
        file2.write_bytes(b"content B")

        hash1 = _compute_file_hash(str(file1))
        hash2 = _compute_file_hash(str(file2))

        assert hash1 != hash2
