from datetime import timedelta
from io import BytesIO
from unittest import mock

import pytest
from fastapi import status

from config import OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS
from handler.auth import oauth_handler
from handler.auth.constants import Scope
from handler.database import (
    db_device_handler,
    db_device_save_sync_handler,
    db_save_handler,
)
from models.assets import Save
from models.device import Device
from models.platform import Platform
from models.rom import Rom
from models.user import User


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
    return oauth_handler.create_access_token(
        data={
            "sub": admin_user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(scopes),
        },
        expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
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

    def test_get_saves_lists_all_device_syncs(
        self, client, access_token: str, admin_user: User, save: Save, device: Device
    ):
        creator = db_device_handler.add_device(
            Device(id="creator-device", user_id=admin_user.id, name="Creator Device")
        )
        # Creator synced at save creation: stays current. Caller is stale.
        db_device_save_sync_handler.upsert_sync(
            device_id=creator.id, save_id=save.id, synced_at=save.updated_at
        )
        db_device_save_sync_handler.upsert_sync(
            device_id=device.id,
            save_id=save.id,
            synced_at=save.updated_at - timedelta(days=1),
        )

        response = client.get(
            f"/api/saves?device_id={device.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        syncs = data[0]["device_syncs"]
        assert len(syncs) == 2

        # Caller's own entry is emitted first for old-client compatibility.
        assert syncs[0]["device_id"] == device.id
        assert syncs[0]["is_current"] is False

        by_id = {s["device_id"]: s for s in syncs}
        assert by_id[creator.id]["device_name"] == "Creator Device"
        assert by_id[creator.id]["is_current"] is True

    def test_get_saves_without_device_id_omits_device_syncs(
        self, client, access_token: str, admin_user: User, save: Save, device: Device
    ):
        creator = db_device_handler.add_device(
            Device(id="creator-device", user_id=admin_user.id, name="Creator Device")
        )
        db_device_save_sync_handler.upsert_sync(
            device_id=creator.id, save_id=save.id, synced_at=save.updated_at
        )
        db_device_save_sync_handler.upsert_sync(device_id=device.id, save_id=save.id)

        response = client.get(
            "/api/saves",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Device attribution is only returned to a device-scoped caller, so a
        # request without device_id omits device_syncs even when syncs exist.
        assert data[0]["device_syncs"] == []

    def test_get_single_save_lists_all_device_syncs(
        self, client, access_token: str, admin_user: User, save: Save, device: Device
    ):
        creator = db_device_handler.add_device(
            Device(id="creator-device", user_id=admin_user.id, name="Creator Device")
        )
        db_device_save_sync_handler.upsert_sync(
            device_id=creator.id, save_id=save.id, synced_at=save.updated_at
        )

        response = client.get(
            f"/api/saves/{save.id}?device_id={device.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        syncs = data["device_syncs"]
        # Caller (no sync row yet) plus the creator device.
        assert {s["device_id"] for s in syncs} == {device.id, creator.id}
        assert syncs[0]["device_id"] == device.id
        by_id = {s["device_id"]: s for s in syncs}
        assert by_id[creator.id]["is_current"] is True
        assert by_id[device.id]["is_current"] is False

    def test_device_syncs_surface_per_device_is_untracked(
        self, client, access_token: str, admin_user: User, save: Save, device: Device
    ):
        other = db_device_handler.add_device(
            Device(id="untracked-other", user_id=admin_user.id, name="Other")
        )
        db_device_save_sync_handler.upsert_sync(device_id=device.id, save_id=save.id)
        db_device_save_sync_handler.set_untracked(
            device_id=other.id, save_id=save.id, untracked=True
        )

        response = client.get(
            f"/api/saves/{save.id}?device_id={device.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        by_id = {s["device_id"]: s for s in response.json()["device_syncs"]}
        # Each device carries its own tracking flag.
        assert by_id[device.id]["is_untracked"] is False
        assert by_id[other.id]["is_untracked"] is True

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
        assert data["origin_device_id"] is None

    @mock.patch(
        "endpoints.saves.fs_asset_handler.remove_file", new_callable=mock.AsyncMock
    )
    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_reupload_updates_file_path_and_emulator(
        self,
        mock_scan,
        _mock_write,
        mock_remove,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
    ):
        """Re-uploading the same filename under a different emulator must move
        the row's file_path/emulator to where the new bytes landed, so the
        stored hash never disagrees with the served content."""
        existing = db_save_handler.add_save(
            Save(
                file_name="test.sav",
                file_name_no_tags="test",
                file_name_no_ext="test",
                file_extension="sav",
                file_path=f"{platform.slug}/saves/old_emu",
                file_size_bytes=100,
                content_hash="0" * 32,
                emulator="old_emu",
                rom_id=rom.id,
                user_id=admin_user.id,
            )
        )

        new_path = f"{platform.slug}/saves/new_emu"
        mock_scan.return_value = Save(
            file_name="test.sav",
            file_name_no_tags="test",
            file_name_no_ext="test",
            file_extension="sav",
            file_path=new_path,
            file_size_bytes=200,
            content_hash="f" * 32,
            rom_id=rom.id,
            user_id=admin_user.id,
        )

        response = client.post(
            f"/api/saves?rom_id={rom.id}&emulator=new_emu",
            files={
                "saveFile": (
                    "test.sav",
                    BytesIO(b"new save data"),
                    "application/octet-stream",
                )
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK

        updated = db_save_handler.get_save(user_id=admin_user.id, id=existing.id)
        assert updated is not None
        assert updated.file_path == new_path
        assert updated.emulator == "new_emu"
        assert updated.content_hash == "f" * 32
        assert updated.file_size_bytes == 200
        # full_path now points at the freshly written bytes, not the stale ones.
        assert updated.full_path == f"{new_path}/test.sav"
        # The orphaned bytes at the old location are cleaned up.
        mock_remove.assert_awaited_once_with(f"{platform.slug}/saves/old_emu/test.sav")

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
        # The creating device is recorded as the save's origin. Its name is
        # resolvable from device_syncs (or /api/devices), so it is not repeated.
        assert data["origin_device_id"] == device.id
        origin_sync = next(
            s for s in data["device_syncs"] if s["device_id"] == device.id
        )
        assert origin_sync["device_name"] == device.name

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_origin_device_persists_for_other_caller(
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
        mock_scan.return_value = Save(
            file_name="origin.sav",
            file_name_no_tags="origin",
            file_name_no_ext="origin",
            file_extension="sav",
            file_path=f"{platform.slug}/saves",
            file_size_bytes=100,
            rom_id=rom.id,
            user_id=admin_user.id,
        )

        # Device A creates the save.
        created = client.post(
            f"/api/saves?rom_id={rom.id}&device_id={device.id}",
            files={"saveFile": ("origin.sav", BytesIO(b"data"), "application/octet")},
            headers={"Authorization": f"Bearer {access_token}"},
        ).json()
        save_id = created["id"]

        # Device B later syncs the current version (download path) and so is also
        # "current", but it did not create the save.
        other = db_device_handler.add_device(
            Device(id="downloader-device", user_id=admin_user.id, name="Downloader")
        )
        db_device_save_sync_handler.upsert_sync(
            device_id=other.id, save_id=save_id, synced_at=None
        )

        response = client.get(
            f"/api/saves/{save_id}?device_id={other.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        by_id = {s["device_id"]: s for s in data["device_syncs"]}
        # Both devices read as current, but origin still points at the creator.
        assert by_id[device.id]["is_current"] is True
        assert by_id[other.id]["is_current"] is True
        assert data["origin_device_id"] == device.id
        assert by_id[device.id]["device_name"] == device.name

    @mock.patch(
        "endpoints.saves.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.saves.scan_save", new_callable=mock.AsyncMock)
    def test_origin_device_unchanged_on_update(
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
        def scanned():
            return Save(
                file_name="origin.sav",
                file_name_no_tags="origin",
                file_name_no_ext="origin",
                file_extension="sav",
                file_path=f"{platform.slug}/saves",
                file_size_bytes=100,
                rom_id=rom.id,
                user_id=admin_user.id,
            )

        # Device A creates the save.
        mock_scan.return_value = scanned()
        created = client.post(
            f"/api/saves?rom_id={rom.id}&device_id={device.id}",
            files={"saveFile": ("origin.sav", BytesIO(b"v1"), "application/octet")},
            headers={"Authorization": f"Bearer {access_token}"},
        ).json()
        assert created["origin_device_id"] == device.id

        other = db_device_handler.add_device(
            Device(id="updater-device", user_id=admin_user.id, name="Updater")
        )

        # A second upload of the same save by another device updates content but
        # must not reassign origin away from the creator.
        mock_scan.return_value = scanned()
        updated = client.post(
            f"/api/saves?rom_id={rom.id}&device_id={other.id}&overwrite=true",
            files={"saveFile": ("origin.sav", BytesIO(b"v2"), "application/octet")},
            headers={"Authorization": f"Bearer {access_token}"},
        ).json()
        assert updated["id"] == created["id"]
        assert updated["origin_device_id"] == device.id

        # And an update with no device at all leaves origin intact.
        mock_scan.return_value = scanned()
        no_device = client.post(
            f"/api/saves?rom_id={rom.id}&overwrite=true",
            files={"saveFile": ("origin.sav", BytesIO(b"v3"), "application/octet")},
            headers={"Authorization": f"Bearer {access_token}"},
        ).json()
        assert no_device["origin_device_id"] == device.id

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
        archival_save: Save,
        device: Device,
        device_b: Device,
    ):
        """Scenario 6: Device A uploads, Device B uploads without downloading first.

        Device B has an old sync from before Device A's upload, so conflict.
        Slot-less uploads negotiate against the null-slot (archival) row.
        """
        from datetime import datetime, timedelta, timezone

        old_sync_time = datetime.now(timezone.utc) - timedelta(hours=2)
        db_device_save_sync_handler.upsert_sync(
            device_id=device_b.id, save_id=archival_save.id, synced_at=old_sync_time
        )

        db_device_save_sync_handler.upsert_sync(
            device_id=device.id,
            save_id=archival_save.id,
            synced_at=archival_save.updated_at,
        )

        mock_scan.return_value = archival_save

        file_content = BytesIO(b"stale save from device b")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&device_id={device_b.id}",
            files={
                "saveFile": (
                    archival_save.file_name,
                    file_content,
                    "application/octet-stream",
                )
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
        archival_save: Save,
        device: Device,
    ):
        """Scenario 7: Web UI uploads (no device_id), device with old sync uploads.

        Device A synced the save, then web UI uploaded a new version (without device_id).
        Device A tries to upload without re-downloading - should conflict.
        """
        from datetime import datetime, timedelta, timezone

        old_sync_time = datetime.now(timezone.utc) - timedelta(hours=1)
        db_device_save_sync_handler.upsert_sync(
            device_id=device.id, save_id=archival_save.id, synced_at=old_sync_time
        )

        mock_scan.return_value = archival_save

        file_content = BytesIO(b"stale save from device after web update")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&device_id={device.id}",
            files={
                "saveFile": (
                    archival_save.file_name,
                    file_content,
                    "application/octet-stream",
                )
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
        archival_save: Save,
        device: Device,
    ):
        """Verify conflict response contains all necessary details for client handling."""
        from datetime import datetime, timedelta, timezone

        old_sync_time = datetime.now(timezone.utc) - timedelta(hours=1)
        db_device_save_sync_handler.upsert_sync(
            device_id=device.id, save_id=archival_save.id, synced_at=old_sync_time
        )

        mock_scan.return_value = archival_save

        file_content = BytesIO(b"conflicting save")
        response = client.post(
            f"/api/saves?rom_id={rom.id}&device_id={device.id}",
            files={
                "saveFile": (
                    archival_save.file_name,
                    file_content,
                    "application/octet-stream",
                )
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

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
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
        assert sync is not None

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

        assert updated_device is not None
        assert updated_device.last_seen is not None
        if original_last_seen:
            assert updated_device.last_seen > original_last_seen

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

        # The save fixture has slot="autosave"; post to the same slot so the
        # slot-scoped dedupe lookup actually fires. (Different slots are
        # legitimately distinct records per the slot-scoped dedupe contract.)
        response = client.post(
            "/api/saves",
            params={"rom_id": rom.id, "slot": "autosave"},
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
    @mock.patch("handler.filesystem.fs_asset_handler.validate_path")
    async def test_compute_file_hash(self, mock_validate_path, tmp_path):
        from handler.filesystem import fs_asset_handler

        test_file = tmp_path / "test.sav"
        test_file.write_bytes(b"test content for hashing")
        mock_validate_path.return_value = test_file

        hash_result = await fs_asset_handler._compute_file_hash(str(test_file))

        assert hash_result is not None
        assert len(hash_result) == 32

        hash_result2 = await fs_asset_handler._compute_file_hash(str(test_file))
        assert hash_result == hash_result2

    @mock.patch("handler.filesystem.fs_asset_handler.validate_path")
    async def test_same_content_produces_same_hash(self, mock_validate_path, tmp_path):
        from handler.filesystem import fs_asset_handler

        file1 = tmp_path / "save1.sav"
        file2 = tmp_path / "save2.sav"
        file1.write_bytes(b"identical content")
        file2.write_bytes(b"identical content")
        mock_validate_path.side_effect = [file1, file2]

        hash1 = await fs_asset_handler._compute_file_hash(str(file1))
        hash2 = await fs_asset_handler._compute_file_hash(str(file2))

        assert hash1 == hash2

    @mock.patch("handler.filesystem.fs_asset_handler.validate_path")
    async def test_different_content_produces_different_hash(
        self, mock_validate_path, tmp_path
    ):
        from handler.filesystem import fs_asset_handler

        file1 = tmp_path / "save1.sav"
        file2 = tmp_path / "save2.sav"
        file1.write_bytes(b"content A")
        file2.write_bytes(b"content B")
        mock_validate_path.side_effect = [file1, file2]

        hash1 = await fs_asset_handler._compute_file_hash(str(file1))
        hash2 = await fs_asset_handler._compute_file_hash(str(file2))

        assert hash1 != hash2


def _build_fixture_a_zip() -> bytes:
    """Single-entry zip; pinned digest b3636b49ca5c3d807adee33e75d410ca."""
    import zipfile

    from tests._zipfile_shim import reload_zipfile

    reload_zipfile()
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("save.bin", b"\x42" * 256)
    return buf.getvalue()


def _build_fixture_b_zip() -> bytes:
    """Three-entry zip with a subdir; pinned digest 8cf6bb36a82a5ee4d7d15fc98599908d."""
    import zipfile

    from tests._zipfile_shim import reload_zipfile

    reload_zipfile()
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("inner/a.txt", b"alpha")
        zf.writestr("inner/b.txt", b"beta")
        zf.writestr("top.bin", b"\x00\x01\x02")
    return buf.getvalue()


def _build_fixture_c_zip() -> bytes:
    """Switch-shaped nested zip; pinned digest c0c992d1f1f883f56065bb13b68dfdee."""
    import zipfile

    from tests._zipfile_shim import reload_zipfile

    reload_zipfile()
    buf = BytesIO()
    title = "0100F2C0115B6000"
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr(f"{title}/NX6400000-SYSTEM/SYDAT.BIN", b"system data v1")
        zf.writestr(f"{title}/album/000_Photo.jpg", b"\xff\xd8\xff\xe0jpegdata" * 8)
        zf.writestr(f"{title}/album/000_Thumb.jpg", b"\xff\xd8thumbdata")
        zf.writestr(f"{title}/slot_01/caption.sav", b"slot1 caption")
        zf.writestr(f"{title}/slot_01/progress.sav", b"\x01" * 64)
        zf.writestr(f"{title}/slot_02/caption.sav", b"slot2 caption")
        zf.writestr(f"{title}/slot_02/progress.sav", b"\x02" * 64)
        zf.writestr(f"{title}/storage/CacheStorageKey.dat", b"key=abcd1234")
        zf.writestr(f"{title}/storage/empty.dat", b"")
        zf.writestr(f"{title}/Pokémon.dat", b"unicode-name")
    return buf.getvalue()


FIXTURE_A_HASH = "b3636b49ca5c3d807adee33e75d410ca"
FIXTURE_B_HASH = "8cf6bb36a82a5ee4d7d15fc98599908d"
FIXTURE_C_HASH = "c0c992d1f1f883f56065bb13b68dfdee"


@pytest.fixture
def _isolated_assets_dir(tmp_path, monkeypatch):
    """Redirect the shared fs_asset_handler to a tmp dir for the test's duration.

    Upload, scan, compute_content_hash, and remove_file all dispatch through
    self.base_path; rebinding base_path to a tmp dir keeps the test from
    leaking files into the real ROMM_BASE_PATH and lets every IO path resolve
    consistently.
    """
    from pathlib import Path

    from handler.filesystem import fs_asset_handler

    new_base = Path(tmp_path).resolve()
    monkeypatch.setattr(fs_asset_handler, "base_path", new_base)
    return new_base


class TestUploadHashContract:
    """Round-trip a real zip through the upload endpoint and pin the
    content_hash the server stores.

    The compute_content_hash path-resolution bug (commit 7996c1293) lived
    precisely here: scan_save -> compute_content_hash -> is_zipfile. Mocking
    scan_save or compute_content_hash defeats the purpose. These tests
    intentionally exercise the unmocked pipeline so any regression in zip
    detection, per-entry hash assembly, or path handling fails loudly.
    """

    def _upload(
        self,
        client,
        access_token: str,
        rom: Rom,
        payload: bytes,
        filename: str,
        slot: str = "autosave",
    ):
        return client.post(
            f"/api/saves?rom_id={rom.id}&slot={slot}&emulator=test_emulator",
            files={
                "saveFile": (filename, BytesIO(payload), "application/octet-stream")
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

    def test_fixture_a_round_trip_pins_hash(
        self,
        client,
        access_token: str,
        rom: Rom,
        _isolated_assets_dir,
    ):
        payload = _build_fixture_a_zip()
        response = self._upload(client, access_token, rom, payload, "fixture_a.zip")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["content_hash"] == FIXTURE_A_HASH

    def test_fixture_b_round_trip_pins_hash(
        self,
        client,
        access_token: str,
        rom: Rom,
        _isolated_assets_dir,
    ):
        payload = _build_fixture_b_zip()
        response = self._upload(client, access_token, rom, payload, "fixture_b.zip")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["content_hash"] == FIXTURE_B_HASH

    def test_fixture_c_round_trip_pins_hash(
        self,
        client,
        access_token: str,
        rom: Rom,
        _isolated_assets_dir,
    ):
        payload = _build_fixture_c_zip()
        response = self._upload(client, access_token, rom, payload, "fixture_c.zip")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["content_hash"] == FIXTURE_C_HASH

    def test_identical_repost_to_same_slot_dedupes_to_first_id(
        self,
        client,
        access_token: str,
        rom: Rom,
        _isolated_assets_dir,
    ):
        """Second upload of identical bytes to the same slot should return the
        first record's id (server-side dedupe via content_hash)."""
        payload = _build_fixture_a_zip()

        first = self._upload(client, access_token, rom, payload, "fixture_a.zip")
        assert first.status_code == status.HTTP_200_OK
        first_id = first.json()["id"]

        second = self._upload(client, access_token, rom, payload, "fixture_a.zip")
        assert second.status_code == status.HTTP_200_OK
        assert second.json()["id"] == first_id
        assert second.json()["content_hash"] == FIXTURE_A_HASH


class TestSlotScopedDedupeMatrix:
    """Verify the slot-scoped content_hash dedupe rules.

    Pre-fix, get_save_by_content_hash ignored slot, so identical bytes uploaded
    to different slots collapsed into one record (breaking clone-save-to-new-
    slot). Each scenario below pins one cell of the truth table.
    """

    def _upload(
        self,
        client,
        access_token: str,
        rom: Rom,
        payload: bytes,
        slot: str,
        filename: str = "matrix.zip",
    ):
        return client.post(
            f"/api/saves?rom_id={rom.id}&slot={slot}&emulator=test_emulator",
            files={
                "saveFile": (filename, BytesIO(payload), "application/octet-stream")
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

    def test_same_bytes_same_slot_dedupes(
        self,
        client,
        access_token: str,
        rom: Rom,
        _isolated_assets_dir,
    ):
        payload = _build_fixture_a_zip()

        first = self._upload(client, access_token, rom, payload, slot="slot1")
        second = self._upload(client, access_token, rom, payload, slot="slot1")

        assert first.status_code == status.HTTP_200_OK
        assert second.status_code == status.HTTP_200_OK
        assert second.json()["id"] == first.json()["id"]

    def test_same_bytes_different_slots_creates_distinct_records(
        self,
        client,
        access_token: str,
        rom: Rom,
        _isolated_assets_dir,
    ):
        """Clone-save-to-new-slot must yield a separate DB row.

        Pre-fix this case incorrectly returned the first slot's id because the
        DAO dropped the slot filter from the content_hash lookup.
        """
        payload = _build_fixture_a_zip()

        first = self._upload(client, access_token, rom, payload, slot="slot1")
        second = self._upload(client, access_token, rom, payload, slot="slot2")

        assert first.status_code == status.HTTP_200_OK
        assert second.status_code == status.HTTP_200_OK
        assert second.json()["id"] != first.json()["id"]
        assert second.json()["slot"] == "slot2"
        assert second.json()["content_hash"] == first.json()["content_hash"]

    def test_slotless_upload_over_named_slot_file_refreshes_that_row(
        self,
        client,
        access_token: str,
        rom: Rom,
        _isolated_assets_dir,
    ):
        """A slot-less upload that lands on a named slot's file (same emulator
        and filename) must not leave that row reporting a stale hash.

        File identity is path+name, independent of slot, so writing new bytes
        there overwrites the named slot's file. The colliding row is refreshed
        in place rather than shadowed by a divergent null-slot duplicate.
        """
        slotted = self._upload(
            client, access_token, rom, _build_fixture_a_zip(), slot="slot1"
        )
        assert slotted.status_code == status.HTTP_200_OK
        shared_name = slotted.json()["file_name"]

        # Slot-less upload (slot param omitted) reusing the slot's on-disk
        # filename, but with new bytes.
        slotless = client.post(
            f"/api/saves?rom_id={rom.id}&emulator=test_emulator",
            files={
                "saveFile": (
                    shared_name,
                    BytesIO(_build_fixture_b_zip()),
                    "application/octet-stream",
                )
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert slotless.status_code == status.HTTP_200_OK
        assert slotless.json()["id"] == slotted.json()["id"]
        assert slotless.json()["content_hash"] == FIXTURE_B_HASH

        # No divergent second row was created for the same file.
        listing = client.get(
            f"/api/saves?rom_id={rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert listing.status_code == status.HTTP_200_OK
        rows = [s for s in listing.json() if s["file_name"] == shared_name]
        assert len(rows) == 1
        assert rows[0]["content_hash"] == FIXTURE_B_HASH

    def test_different_bytes_same_slot_creates_distinct_records(
        self,
        client,
        access_token: str,
        rom: Rom,
        _isolated_assets_dir,
    ):
        """No false-positive dedupe across distinct content within one slot."""
        import zipfile

        from tests._zipfile_shim import reload_zipfile

        payload_a = _build_fixture_a_zip()

        reload_zipfile()
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
            zf.writestr("save.bin", b"\x43" * 256)
        payload_b = buf.getvalue()

        first = self._upload(
            client, access_token, rom, payload_a, slot="slot1", filename="a.zip"
        )
        second = self._upload(
            client, access_token, rom, payload_b, slot="slot1", filename="b.zip"
        )

        assert first.status_code == status.HTTP_200_OK
        assert second.status_code == status.HTTP_200_OK
        assert second.json()["id"] != first.json()["id"]
        assert second.json()["content_hash"] != first.json()["content_hash"]


class TestSaveVisibilityPropagation:
    """Sharing a save should also publish its auto-captured thumbnail, so other
    users still see the preview alongside the shared save."""

    def test_sharing_save_syncs_thumbnail_visibility(
        self,
        client,
        access_token: str,
        save: Save,
        rom: Rom,
        platform: Platform,
        admin_user: User,
    ):
        from handler.database import db_screenshot_handler
        from models.assets import Screenshot

        # Thumbnail whose filename stem matches the save (how Save.screenshot links).
        thumb = db_screenshot_handler.add_screenshot(
            Screenshot(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="test_save.png",
                file_path=f"{platform.slug}/screenshots",
                file_size_bytes=1,
                is_public=False,
            )
        )

        response = client.put(
            f"/api/saves/{save.id}/visibility",
            json={"is_public": True},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_public"] is True

        refreshed = db_screenshot_handler.get_screenshot_by_id(thumb.id)
        assert refreshed is not None and refreshed.is_public is True

        # Un-sharing flips the thumbnail back to private too.
        client.put(
            f"/api/saves/{save.id}/visibility",
            json={"is_public": False},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        refreshed = db_screenshot_handler.get_screenshot_by_id(thumb.id)
        assert refreshed is not None and refreshed.is_public is False
