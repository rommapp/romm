from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from endpoints.device import consoles as consoles_endpoints
from handler.auth.base_handler import oauth_handler
from handler.database import db_device_handler
from handler.sync.console import sync_handler
from handler.sync.console.common import ConsoleProbeResult, ConsoleUserProfile
from handler.sync.console.ps3 import PS3
from handler.sync.console.ps4 import PS4
from models.device import Device, SyncMode
from models.user import User


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def ps3_device(admin_user: User) -> Device:
    return db_device_handler.add_device(
        Device(
            id="ps3-device",
            user_id=admin_user.id,
            name="PS3",
            client=PS3.device_type.client,
            sync_mode=SyncMode.PUSH_PULL,
            ip_address="192.168.1.115",
            sync_config={"user_id": "00000001", "poll_interval_minutes": 30},
        )
    )


@pytest.fixture
def enqueue():
    with patch.object(sync_handler, "high_prio_queue", MagicMock()) as queue:
        yield queue.enqueue


class TestAddConsole:
    def test_rejects_a_console_it_cannot_sync(self, client, access_token: str):
        response = client.post(
            "/api/devices/consoles",
            json={"console": "xbox", "name": "X", "ip_address": "192.168.1.9"},
            headers=auth(access_token),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.parametrize(
        ("console", "user_id", "platform", "ftp_port"),
        [("ps3", "00000001", "PS3", 21), ("ps4", "1cabafc9", "PS4", 2121)],
    )
    def test_adds_a_push_pull_console(
        self,
        client,
        access_token: str,
        console: str,
        user_id: str,
        platform: str,
        ftp_port: int,
    ):
        response = client.post(
            "/api/devices/consoles",
            json={
                "console": console,
                "name": "Living room",
                "ip_address": "192.168.1.115",
                "user_id": user_id,
            },
            headers=auth(access_token),
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["client"] == console
        assert data["platform"] == platform
        assert data["sync_mode"] == "push_pull"
        assert data["ip_address"] == "192.168.1.115"
        assert data["sync_config"] == {
            "ftp_port": ftp_port,
            "user_id": user_id,
            "poll_interval_minutes": 15,
            "keep_versions": 10,
        }

    @pytest.mark.parametrize("address", ["8.8.8.8", "127.0.0.1", "not-an-ip"])
    def test_rejects_an_address_off_the_local_network(
        self, client, access_token: str, address: str
    ):
        response = client.post(
            "/api/devices/consoles",
            json={
                "console": "ps3",
                "name": "PS3",
                "ip_address": address,
                "user_id": "00000001",
            },
            headers=auth(access_token),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.parametrize(
        ("console", "user_id"),
        [("ps3", "1"), ("ps3", "1cabafc9"), ("ps4", "1CABAFC9"), ("ps4", None)],
    )
    def test_rejects_an_invalid_user_profile(
        self, client, access_token: str, console: str, user_id: str | None
    ):
        response = client.post(
            "/api/devices/consoles",
            json={
                "console": console,
                "name": "Console",
                "ip_address": "10.0.0.2",
                "user_id": user_id,
            },
            headers=auth(access_token),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestUpdateConsole:
    def test_updates_only_what_is_sent(
        self, client, access_token: str, ps3_device: Device
    ):
        response = client.put(
            f"/api/devices/consoles/{ps3_device.id}",
            json={"keep_versions": 3, "ip_address": "192.168.1.20"},
            headers=auth(access_token),
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["ip_address"] == "192.168.1.20"
        assert data["sync_config"]["keep_versions"] == 3
        assert data["sync_config"]["poll_interval_minutes"] == 30

    def test_keeps_the_profile(self, client, access_token: str, ps3_device: Device):
        response = client.put(
            f"/api/devices/consoles/{ps3_device.id}",
            json={"user_id": "00000002"},
            headers=auth(access_token),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["sync_config"] == ps3_device.sync_config

    def test_not_found_for_another_kind_of_device(
        self, client, access_token: str, admin_user: User
    ):
        db_device_handler.add_device(
            Device(id="phone", user_id=admin_user.id, client="argosy-launcher")
        )
        response = client.put(
            "/api/devices/consoles/phone",
            json={"name": "x"},
            headers=auth(access_token),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_not_found_for_another_user(
        self, client, editor_user: User, ps3_device: Device
    ):
        token = oauth_handler.create_access_token(
            data={
                "sub": editor_user.username,
                "iss": "romm:oauth",
                "scopes": " ".join(editor_user.oauth_scopes),
            },
            expires_delta=timedelta(minutes=5),
        )
        response = client.put(
            f"/api/devices/consoles/{ps3_device.id}",
            json={"name": "mine now"},
            headers=auth(token),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestGenericDeviceRoutes:
    def test_cannot_register_a_console(self, client, access_token: str):
        response = client.post(
            "/api/devices",
            json={"client": "ps3", "sync_mode": "push_pull", "ip_address": "127.0.0.1"},
            headers=auth(access_token),
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.parametrize(
        "change",
        [{"ip_address": "127.0.0.1"}, {"sync_config": {"user_id": "00000002"}}],
    )
    def test_cannot_retarget_a_console(
        self, client, access_token: str, ps3_device: Device, change: dict[str, object]
    ):
        response = client.put(
            f"/api/devices/{ps3_device.id}", json=change, headers=auth(access_token)
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_still_toggle_and_rename_a_console(
        self, client, access_token: str, ps3_device: Device
    ):
        response = client.put(
            f"/api/devices/{ps3_device.id}",
            json={"sync_enabled": False, "name": "Upstairs"},
            headers=auth(access_token),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["sync_enabled"] is False

    def test_cannot_turn_a_device_into_a_console(
        self, client, access_token: str, admin_user: User
    ):
        db_device_handler.add_device(Device(id="phone", user_id=admin_user.id))
        response = client.put(
            "/api/devices/phone", json={"client": "ps3"}, headers=auth(access_token)
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestProbeConsole:
    def test_reports_the_console(self, client, access_token: str):
        result = ConsoleProbeResult(
            reachable=True,
            is_ftp=True,
            users=[ConsoleUserProfile(id="00000001", name="FIL2K")],
        )
        with patch.object(
            consoles_endpoints, "probe_console_ftp", AsyncMock(return_value=result)
        ) as probe:
            response = client.post(
                "/api/devices/consoles/probe",
                json={"console": "ps3", "ip_address": "192.168.1.115"},
                headers=auth(access_token),
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "reachable": True,
            "is_ftp": True,
            "users": [{"id": "00000001", "name": "FIL2K"}],
        }
        probe.assert_awaited_once_with(PS3, "192.168.1.115", 21)

    def test_probes_a_ps4_on_its_ftp_port(self, client, access_token: str):
        result = ConsoleProbeResult(reachable=True, is_ftp=True, users=[])
        with patch.object(
            consoles_endpoints, "probe_console_ftp", AsyncMock(return_value=result)
        ) as probe:
            response = client.post(
                "/api/devices/consoles/probe",
                json={"console": "ps4", "ip_address": "192.168.1.177"},
                headers=auth(access_token),
            )

        assert response.status_code == status.HTTP_200_OK
        probe.assert_awaited_once_with(PS4, "192.168.1.177", 2121)

    def test_rejects_a_public_address(self, client, access_token: str):
        response = client.post(
            "/api/devices/consoles/probe",
            json={"console": "ps3", "ip_address": "1.1.1.1"},
            headers=auth(access_token),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestSyncConsole:
    def test_queues_a_sync(
        self, client, access_token: str, ps3_device: Device, enqueue
    ):
        response = client.post(
            f"/api/devices/consoles/{ps3_device.id}/sync",
            headers=auth(access_token),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["device_id"] == ps3_device.id
        enqueue.assert_called_once()
        assert enqueue.call_args.kwargs["device_id"] == ps3_device.id
        assert enqueue.call_args.kwargs["force"] is True

    def test_refuses_a_console_with_sync_off(
        self, client, access_token: str, ps3_device: Device, enqueue
    ):
        db_device_handler.update_device(
            device_id=ps3_device.id,
            user_id=ps3_device.user_id,
            data={"sync_enabled": False},
        )
        response = client.post(
            f"/api/devices/consoles/{ps3_device.id}/sync",
            headers=auth(access_token),
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        enqueue.assert_not_called()
