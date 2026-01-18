from datetime import timedelta

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from main import app

from endpoints.auth import ACCESS_TOKEN_EXPIRE_MINUTES
from handler.auth import oauth_handler
from handler.database import db_device_handler
from handler.redis_handler import sync_cache
from models.device import Device
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
def editor_access_token(editor_user: User):
    return oauth_handler.create_oauth_token(
        data={
            "sub": editor_user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(editor_user.oauth_scopes),
            "type": "access",
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )


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
