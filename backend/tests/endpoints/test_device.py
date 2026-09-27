import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import status

from endpoints import device as device_endpoints
from handler.database import db_device_handler
from handler.device_install_handler import device_install_handler
from handler.redis_handler import sync_cache
from models.device import Device
from models.user import User


class TestDeviceEndpoints:
    def test_register_device(self, client, access_token: str):
        response = client.post(
            "/api/devices",
            json={
                "name": "Test Device",
                "platform": "android",
                "client": "argosy",
                "client_version": "0.16.0",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Test Device"
        assert "device_id" in data
        assert "created_at" in data

    def test_register_device_minimal(self, client, access_token: str):
        response = client.post(
            "/api/devices",
            json={},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] is None
        assert "device_id" in data

    def test_list_devices(self, client, access_token: str, admin_user: User):
        db_device_handler.add_device(
            Device(
                id="test-device-1",
                user_id=admin_user.id,
                name="Device 1",
            )
        )
        db_device_handler.add_device(
            Device(
                id="test-device-2",
                user_id=admin_user.id,
                name="Device 2",
            )
        )

        response = client.get(
            "/api/devices",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        names = [d["name"] for d in data]
        assert "Device 1" in names
        assert "Device 2" in names

    def test_get_device(self, client, access_token: str, admin_user: User):
        device = db_device_handler.add_device(
            Device(
                id="test-device-get",
                user_id=admin_user.id,
                name="Get Test Device",
                platform="linux",
            )
        )

        response = client.get(
            f"/api/devices/{device.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == "test-device-get"
        assert data["name"] == "Get Test Device"
        assert data["platform"] == "linux"

    def test_get_device_not_found(self, client, access_token: str):
        response = client.get(
            "/api/devices/nonexistent-device",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_device(self, client, access_token: str, admin_user: User):
        device = db_device_handler.add_device(
            Device(
                id="test-device-update",
                user_id=admin_user.id,
                name="Original Name",
            )
        )

        response = client.put(
            f"/api/devices/{device.id}",
            json={
                "name": "Updated Name",
                "platform": "android",
                "client": "daijishou",
                "client_version": "4.0.0",
                "ip_address": "192.168.1.100",
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "hostname": "my-odin3",
                "sync_enabled": False,
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["platform"] == "android"
        assert data["client"] == "daijishou"
        assert data["client_version"] == "4.0.0"
        assert data["ip_address"] == "192.168.1.100"
        assert data["mac_address"] == "AA:BB:CC:DD:EE:FF"
        assert data["hostname"] == "my-odin3"
        assert data["sync_enabled"] is False

    def test_delete_device(self, client, access_token: str, admin_user: User):
        device = db_device_handler.add_device(
            Device(
                id="test-device-delete",
                user_id=admin_user.id,
                name="To Delete",
            )
        )

        response = client.delete(
            f"/api/devices/{device.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        get_response = client.get(
            f"/api/devices/{device.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_device_exposes_client_device_identifier(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(
                id="test-device-cid",
                user_id=admin_user.id,
                name="CID Device",
                client_device_identifier="install-uuid-abc123",
            )
        )

        response = client.get(
            f"/api/devices/{device.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["client_device_identifier"] == "install-uuid-abc123"

    def test_deleting_a_device_closes_its_token_sockets(
        self, mocker, client, access_token: str, admin_user: User, add_device_token
    ):
        device = db_device_handler.add_device(
            Device(id="test-device-sockets", user_id=admin_user.id, name="Handheld")
        )
        token, _ = add_device_token(admin_user, device.id, scopes="devices.read")
        close = mocker.patch.object(
            device_endpoints, "close_client_token_sockets", AsyncMock()
        )

        response = client.delete(
            f"/api/devices/{device.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        close.assert_awaited_once_with([token.id])

    def test_deleting_a_device_drops_its_install_requests(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(id="test-device-installs", user_id=admin_user.id, name="Handheld")
        )
        install, _ = asyncio.run(
            device_install_handler.create(
                user_id=admin_user.id, device_id=device.id, rom_id=7, file_ids=[1]
            )
        )

        response = client.delete(
            f"/api/devices/{device.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert asyncio.run(device_install_handler.get(install.id)) is None
        assert asyncio.run(device_install_handler.list_for_rom(admin_user.id, 7)) == []


class TestDeviceCapabilities:
    def test_registering_stores_the_reported_capabilities(
        self, client, access_token: str, admin_user: User
    ):
        response = client.post(
            "/api/devices",
            json={"name": "Handheld", "capabilities": {"remote_install": True}},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        stored = db_device_handler.get_device(
            device_id=response.json()["device_id"], user_id=admin_user.id
        )
        assert stored is not None
        assert stored.capabilities == {"remote_install": True}

    def test_registering_again_replaces_the_capabilities(
        self, client, access_token: str, admin_user: User
    ):
        body = {"name": "Handheld", "hostname": "thor", "platform": "android"}
        headers = {"Authorization": f"Bearer {access_token}"}
        first = client.post(
            "/api/devices",
            json={**body, "capabilities": {"remote_install": False}},
            headers=headers,
        )

        again = client.post(
            "/api/devices",
            json={**body, "capabilities": {"remote_install": True}},
            headers=headers,
        )

        assert again.status_code == status.HTTP_200_OK
        assert again.json()["device_id"] == first.json()["device_id"]
        stored = db_device_handler.get_device(
            device_id=first.json()["device_id"], user_id=admin_user.id
        )
        assert stored is not None
        assert stored.capabilities == {"remote_install": True}

    def test_updating_replaces_the_capabilities(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(id="test-device-caps", user_id=admin_user.id, name="Handheld")
        )

        response = client.put(
            f"/api/devices/{device.id}",
            json={"capabilities": {"remote_install": True}},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["capabilities"] == {"remote_install": True}

    def test_an_update_without_capabilities_keeps_them(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(id="test-device-keep-caps", user_id=admin_user.id, name="Handheld")
        )
        headers = {"Authorization": f"Bearer {access_token}"}
        client.put(
            f"/api/devices/{device.id}",
            json={"capabilities": {"remote_install": True}},
            headers=headers,
        )

        response = client.put(
            f"/api/devices/{device.id}",
            json={"name": "Renamed", "client_version": "2.18.0"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["capabilities"] == {"remote_install": True}
        stored = db_device_handler.get_device(
            device_id=device.id, user_id=admin_user.id
        )
        assert stored is not None
        assert stored.capabilities == {"remote_install": True}

    def test_registering_again_without_capabilities_keeps_them(
        self, client, access_token: str, admin_user: User
    ):
        body = {"name": "Handheld", "hostname": "thor", "platform": "android"}
        headers = {"Authorization": f"Bearer {access_token}"}
        first = client.post(
            "/api/devices",
            json={**body, "capabilities": {"remote_install": True}},
            headers=headers,
        )

        again = client.post("/api/devices", json=body, headers=headers)

        assert again.status_code == status.HTTP_200_OK
        stored = db_device_handler.get_device(
            device_id=first.json()["device_id"], user_id=admin_user.id
        )
        assert stored is not None
        assert stored.capabilities == {"remote_install": True}

    @pytest.mark.parametrize(
        "capabilities",
        [
            {"remote_install": "yes"},
            {"": True},
            {"x" * 65: True},
            {f"flag{i}": True for i in range(33)},
        ],
    )
    def test_rejects_capabilities_that_are_not_named_flags(
        self, client, access_token: str, capabilities
    ):
        response = client.post(
            "/api/devices",
            json={"name": "Handheld", "capabilities": capabilities},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestDevicePresence:
    def test_lists_the_callers_devices_holding_a_socket(
        self, client, access_token: str, admin_user: User, editor_user: User
    ):
        for device_id, user in (
            ("dev-online", admin_user),
            ("dev-offline", admin_user),
            ("dev-editor", editor_user),
        ):
            db_device_handler.add_device(Device(id=device_id, user_id=user.id))
        sync_cache.sadd("device_presence:dev-online", "sid-1")
        sync_cache.sadd("device_presence:dev-editor", "sid-2")

        response = client.get(
            "/api/devices/online",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == ["dev-online"]


class TestDeviceUserIsolation:
    def test_list_devices_only_returns_own_devices(
        self,
        client,
        access_token: str,
        editor_access_token: str,
        admin_user: User,
        editor_user: User,
    ):
        db_device_handler.add_device(
            Device(id="admin-device", user_id=admin_user.id, name="Admin Device")
        )
        db_device_handler.add_device(
            Device(id="editor-device", user_id=editor_user.id, name="Editor Device")
        )

        admin_response = client.get(
            "/api/devices",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert admin_response.status_code == status.HTTP_200_OK
        admin_devices = admin_response.json()
        assert len(admin_devices) == 1
        assert admin_devices[0]["name"] == "Admin Device"

        editor_response = client.get(
            "/api/devices",
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )
        assert editor_response.status_code == status.HTTP_200_OK
        editor_devices = editor_response.json()
        assert len(editor_devices) == 1
        assert editor_devices[0]["name"] == "Editor Device"

    def test_cannot_get_other_users_device(
        self,
        client,
        editor_access_token: str,
        admin_user: User,
    ):
        device = db_device_handler.add_device(
            Device(id="admin-only-device", user_id=admin_user.id, name="Admin Only")
        )

        response = client.get(
            f"/api/devices/{device.id}",
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_update_other_users_device(
        self,
        client,
        editor_access_token: str,
        admin_user: User,
    ):
        device = db_device_handler.add_device(
            Device(id="admin-protected-device", user_id=admin_user.id, name="Protected")
        )

        response = client.put(
            f"/api/devices/{device.id}",
            json={"name": "Hacked Name"},
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

        original = db_device_handler.get_device(
            device_id=device.id, user_id=admin_user.id
        )
        assert original is not None
        assert original.name == "Protected"

    def test_cannot_delete_other_users_device(
        self,
        client,
        editor_access_token: str,
        admin_user: User,
    ):
        device = db_device_handler.add_device(
            Device(id="admin-nodelete-device", user_id=admin_user.id, name="No Delete")
        )

        response = client.delete(
            f"/api/devices/{device.id}",
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

        still_exists = db_device_handler.get_device(
            device_id=device.id, user_id=admin_user.id
        )
        assert still_exists is not None


class TestDeviceDuplicateHandling:
    def test_duplicate_mac_address_returns_existing(
        self, client, access_token: str, admin_user: User
    ):
        db_device_handler.add_device(
            Device(
                id="existing-mac-device",
                user_id=admin_user.id,
                name="Existing Device",
                mac_address="AA:BB:CC:DD:EE:FF",
            )
        )

        response = client.post(
            "/api/devices",
            json={
                "name": "New Device",
                "mac_address": "AA:BB:CC:DD:EE:FF",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["device_id"] == "existing-mac-device"
        assert data["name"] == "Existing Device"

    def test_duplicate_hostname_platform_returns_existing(
        self, client, access_token: str, admin_user: User
    ):
        db_device_handler.add_device(
            Device(
                id="existing-hostname-device",
                user_id=admin_user.id,
                name="Existing Device",
                hostname="my-device",
                platform="android",
            )
        )

        response = client.post(
            "/api/devices",
            json={
                "name": "New Device",
                "hostname": "my-device",
                "platform": "android",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["device_id"] == "existing-hostname-device"
        assert data["name"] == "Existing Device"

    def test_duplicate_with_allow_existing_false_returns_409(
        self, client, access_token: str, admin_user: User
    ):
        db_device_handler.add_device(
            Device(
                id="reject-duplicate-device",
                user_id=admin_user.id,
                name="Existing Device",
                mac_address="FF:EE:DD:CC:BB:AA",
            )
        )

        response = client.post(
            "/api/devices",
            json={
                "name": "New Device",
                "mac_address": "FF:EE:DD:CC:BB:AA",
                "allow_existing": False,
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()["detail"]
        assert data["error"] == "device_exists"
        assert data["device_id"] == "reject-duplicate-device"

    def test_allow_existing_returns_existing_device(
        self, client, access_token: str, admin_user: User
    ):
        existing = db_device_handler.add_device(
            Device(
                id="allow-existing-device",
                user_id=admin_user.id,
                name="Existing Device",
                mac_address="11:22:33:44:55:66",
            )
        )

        response = client.post(
            "/api/devices",
            json={
                "name": "New Device Name",
                "mac_address": "11:22:33:44:55:66",
                "allow_existing": True,
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["device_id"] == existing.id
        assert data["name"] == "Existing Device"

    def test_allow_existing_with_reset_syncs(
        self, client, access_token: str, admin_user: User, rom
    ):
        from handler.database import db_device_save_sync_handler, db_save_handler
        from models.assets import Save

        existing = db_device_handler.add_device(
            Device(
                id="reset-syncs-device",
                user_id=admin_user.id,
                name="Device With Syncs",
                mac_address="77:88:99:AA:BB:CC",
            )
        )

        save = db_save_handler.add_save(
            Save(
                file_name="test.sav",
                file_name_no_tags="test",
                file_name_no_ext="test",
                file_extension="sav",
                file_path="/saves",
                file_size_bytes=100,
                rom_id=rom.id,
                user_id=admin_user.id,
            )
        )
        db_device_save_sync_handler.upsert_sync(device_id=existing.id, save_id=save.id)

        sync_before = db_device_save_sync_handler.get_sync(
            device_id=existing.id, save_id=save.id
        )
        assert sync_before is not None

        response = client.post(
            "/api/devices",
            json={
                "mac_address": "77:88:99:AA:BB:CC",
                "allow_existing": True,
                "reset_syncs": True,
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["device_id"] == existing.id

        sync_after = db_device_save_sync_handler.get_sync(
            device_id=existing.id, save_id=save.id
        )
        assert sync_after is None

    def test_allow_duplicate_creates_new_device(
        self, client, access_token: str, admin_user: User
    ):
        existing = db_device_handler.add_device(
            Device(
                id="original-device",
                user_id=admin_user.id,
                name="Original Device",
                mac_address="DD:EE:FF:00:11:22",
            )
        )

        response = client.post(
            "/api/devices",
            json={
                "name": "Duplicate Install",
                "mac_address": "DD:EE:FF:00:11:22",
                "allow_duplicate": True,
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["device_id"] != existing.id
        assert data["name"] == "Duplicate Install"

    def test_no_conflict_without_fingerprint(self, client, access_token: str):
        response1 = client.post(
            "/api/devices",
            json={"name": "Device 1"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response1.status_code == status.HTTP_201_CREATED

        response2 = client.post(
            "/api/devices",
            json={"name": "Device 2"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response2.status_code == status.HTTP_201_CREATED
        assert response1.json()["device_id"] != response2.json()["device_id"]

    def test_hostname_only_no_conflict_without_platform(
        self, client, access_token: str, admin_user: User
    ):
        db_device_handler.add_device(
            Device(
                id="hostname-only-device",
                user_id=admin_user.id,
                name="Existing",
                hostname="my-device",
            )
        )

        response = client.post(
            "/api/devices",
            json={
                "name": "New Device",
                "hostname": "my-device",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_201_CREATED


class TestSyncConfigMasking:
    def test_ssh_credentials_masked_in_response(
        self, client, access_token: str, admin_user: User
    ):
        db_device_handler.add_device(
            Device(
                id="mask-dev-1",
                user_id=admin_user.id,
                name="SSH Device",
                sync_config={
                    "ssh_host": "192.168.1.100",
                    "ssh_port": 22,
                    "ssh_username": "retro",
                    "ssh_password": "supersecret123",
                    "ssh_key_path": "/home/retro/.ssh/id_rsa",
                    "save_directories": [
                        {"platform_slug": "gba", "path": "/saves/gba"}
                    ],
                },
            )
        )

        response = client.get(
            "/api/devices/mask-dev-1",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        config = response.json()["sync_config"]
        assert config["ssh_host"] == "192.168.1.100"
        assert config["ssh_port"] == 22
        assert config["ssh_username"] == "retro"
        assert config["ssh_password"] == "********"
        assert config["ssh_key_path"] == "********"
        assert config["save_directories"] == [
            {"platform_slug": "gba", "path": "/saves/gba"}
        ]

    def test_null_sync_config_passes_through(
        self, client, access_token: str, admin_user: User
    ):
        db_device_handler.add_device(
            Device(
                id="mask-dev-2",
                user_id=admin_user.id,
                name="No Config Device",
            )
        )

        response = client.get(
            "/api/devices/mask-dev-2",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["sync_config"] is None

    def test_sync_config_without_sensitive_fields(
        self, client, access_token: str, admin_user: User
    ):
        db_device_handler.add_device(
            Device(
                id="mask-dev-3",
                user_id=admin_user.id,
                sync_config={"ssh_host": "10.0.0.1", "ssh_port": 2222},
            )
        )

        response = client.get(
            "/api/devices/mask-dev-3",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        config = response.json()["sync_config"]
        assert config["ssh_host"] == "10.0.0.1"
        assert config["ssh_port"] == 2222
