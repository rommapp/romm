import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import status

from handler.database import (
    db_client_token_handler,
    db_device_handler,
    db_rom_handler,
    db_shortcut_handler,
)
from models.client_token import ClientToken
from models.device import Device
from models.rom import Rom
from models.shortcut import ShortcutStatus
from models.user import User


@pytest.fixture(autouse=True)
def silence_socket_emits(monkeypatch):
    """Emits go through a Redis-backed Socket.IO manager; tests only need to
    know they were called."""
    changed = AsyncMock()
    monkeypatch.setattr("endpoints.shortcuts.emit_shortcuts_changed", changed)
    return changed


@pytest.fixture
def device(admin_user: User):
    return db_device_handler.add_device(
        Device(
            id=str(uuid.uuid4()),
            user_id=admin_user.id,
            name="Gaming PC",
            client="steam-companion",
            launch_capabilities={"test_platform_slug": "retroarch:snes9x"},
        )
    )


@pytest.fixture
def device_token(admin_user: User, device: Device):
    """A client token bound to the device, as the companion holds."""
    from handler.auth import auth_handler

    raw = f"rmm_{uuid.uuid4().hex}"
    db_client_token_handler.add_token(
        ClientToken(
            user_id=admin_user.id,
            name="companion",
            hashed_token=auth_handler.hash_client_token(raw),
            scopes="devices.read devices.write roms.user.read roms.user.write",
            device_id=device.id,
        )
    )
    return raw


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestUpsertAndList:
    def test_upsert_queues_pending_add(
        self, client, access_token: str, device: Device, rom: Rom, silence_socket_emits
    ):
        response = client.put(
            "/api/shortcuts",
            json={"device_id": device.id, "rom_id": rom.id},
            headers=_auth(access_token),
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == ShortcutStatus.PENDING_ADD
        assert data["device_id"] == device.id
        assert data["rom_id"] == rom.id
        assert data["launch_mode"] is None
        silence_socket_emits.assert_awaited_once()

    def test_upsert_is_idempotent_and_resets_failure(
        self, client, access_token: str, device: Device, rom: Rom
    ):
        first = client.put(
            "/api/shortcuts",
            json={"device_id": device.id, "rom_id": rom.id},
            headers=_auth(access_token),
        ).json()
        db_shortcut_handler.ack(
            shortcut_id=first["id"], status=ShortcutStatus.FAILED, error="no emulator"
        )

        second = client.put(
            "/api/shortcuts",
            json={
                "device_id": device.id,
                "rom_id": rom.id,
                "launch_mode": "web_player",
            },
            headers=_auth(access_token),
        ).json()
        assert second["id"] == first["id"]
        assert second["status"] == ShortcutStatus.PENDING_ADD
        assert second["error"] is None
        assert second["launch_mode"] == "web_player"

    def test_upsert_unknown_device_is_404(self, client, access_token: str, rom: Rom):
        response = client.put(
            "/api/shortcuts",
            json={"device_id": "nope", "rom_id": rom.id},
            headers=_auth(access_token),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_upsert_unknown_rom_is_404(self, client, access_token: str, device: Device):
        response = client.put(
            "/api/shortcuts",
            json={"device_id": device.id, "rom_id": 999999},
            headers=_auth(access_token),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_filters_by_rom_and_status(
        self, client, access_token: str, device: Device, rom: Rom
    ):
        created = client.put(
            "/api/shortcuts",
            json={"device_id": device.id, "rom_id": rom.id},
            headers=_auth(access_token),
        ).json()

        by_rom = client.get(
            f"/api/shortcuts?rom_id={rom.id}", headers=_auth(access_token)
        )
        assert by_rom.status_code == status.HTTP_200_OK
        assert [s["id"] for s in by_rom.json()] == [created["id"]]

        none_added = client.get(
            f"/api/shortcuts?rom_id={rom.id}&status=added", headers=_auth(access_token)
        )
        assert none_added.json() == []

        bad_status = client.get(
            "/api/shortcuts?status=bogus", headers=_auth(access_token)
        )
        assert bad_status.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_device_me_requires_bound_token(self, client, access_token: str):
        response = client.get(
            "/api/shortcuts?device_id=me", headers=_auth(access_token)
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestCompanionQueueAndAck:
    def test_companion_reads_queue_and_acks_added(
        self, client, access_token: str, device_token: str, device: Device, rom: Rom
    ):
        created = client.put(
            "/api/shortcuts",
            json={"device_id": device.id, "rom_id": rom.id},
            headers=_auth(access_token),
        ).json()

        queue = client.get(
            "/api/shortcuts?device_id=me&status=pending_add,pending_remove,staged",
            headers=_auth(device_token),
        )
        assert queue.status_code == status.HTTP_200_OK
        assert [s["id"] for s in queue.json()] == [created["id"]]

        staged = client.post(
            f"/api/shortcuts/{created['id']}/ack",
            json={"status": "staged"},
            headers=_auth(device_token),
        )
        assert staged.status_code == status.HTTP_200_OK
        assert staged.json()["status"] == ShortcutStatus.STAGED

        added = client.post(
            f"/api/shortcuts/{created['id']}/ack",
            json={"status": "added", "steam_app_id": 0x80003039},
            headers=_auth(device_token),
        )
        assert added.status_code == status.HTTP_200_OK
        assert added.json()["status"] == ShortcutStatus.ADDED
        assert added.json()["steam_app_id"] == 0x80003039

        # Once added, nothing is queued for the device.
        queue = client.get(
            "/api/shortcuts?device_id=me&status=pending_add,pending_remove,staged",
            headers=_auth(device_token),
        )
        assert queue.json() == []

    def test_ack_failed_stores_error(
        self, client, access_token: str, device_token: str, device: Device, rom: Rom
    ):
        created = client.put(
            "/api/shortcuts",
            json={"device_id": device.id, "rom_id": rom.id},
            headers=_auth(access_token),
        ).json()
        response = client.post(
            f"/api/shortcuts/{created['id']}/ack",
            json={"status": "failed", "error": "RetroArch not found"},
            headers=_auth(device_token),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == ShortcutStatus.FAILED
        assert response.json()["error"] == "RetroArch not found"

    def test_ack_from_other_device_token_is_forbidden(
        self, client, access_token: str, admin_user: User, device: Device, rom: Rom
    ):
        from handler.auth import auth_handler

        other = db_device_handler.add_device(
            Device(id=str(uuid.uuid4()), user_id=admin_user.id, name="Laptop")
        )
        raw = f"rmm_{uuid.uuid4().hex}"
        db_client_token_handler.add_token(
            ClientToken(
                user_id=admin_user.id,
                name="laptop",
                hashed_token=auth_handler.hash_client_token(raw),
                scopes="devices.write",
                device_id=other.id,
            )
        )
        created = client.put(
            "/api/shortcuts",
            json={"device_id": device.id, "rom_id": rom.id},
            headers=_auth(access_token),
        ).json()
        response = client.post(
            f"/api/shortcuts/{created['id']}/ack",
            json={"status": "added"},
            headers=_auth(raw),
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestRemove:
    def test_remove_pending_add_deletes_immediately(
        self, client, access_token: str, device: Device, rom: Rom
    ):
        created = client.put(
            "/api/shortcuts",
            json={"device_id": device.id, "rom_id": rom.id},
            headers=_auth(access_token),
        ).json()
        response = client.delete(
            f"/api/shortcuts/{created['id']}", headers=_auth(access_token)
        )
        assert response.status_code == status.HTTP_200_OK
        assert (
            client.get(
                f"/api/shortcuts?rom_id={rom.id}", headers=_auth(access_token)
            ).json()
            == []
        )

    def test_remove_added_goes_through_pending_remove(
        self, client, access_token: str, device_token: str, device: Device, rom: Rom
    ):
        created = client.put(
            "/api/shortcuts",
            json={"device_id": device.id, "rom_id": rom.id},
            headers=_auth(access_token),
        ).json()
        client.post(
            f"/api/shortcuts/{created['id']}/ack",
            json={"status": "added"},
            headers=_auth(device_token),
        )

        removed = client.delete(
            f"/api/shortcuts/{created['id']}", headers=_auth(access_token)
        )
        assert removed.json()["status"] == ShortcutStatus.PENDING_REMOVE

        ack = client.post(
            f"/api/shortcuts/{created['id']}/ack",
            json={"status": "removed"},
            headers=_auth(device_token),
        )
        assert ack.status_code == status.HTTP_200_OK
        assert (
            client.get(
                f"/api/shortcuts?rom_id={rom.id}", headers=_auth(access_token)
            ).json()
            == []
        )


class TestUserIsolation:
    def test_other_user_cannot_see_or_target_device(
        self,
        client,
        access_token: str,
        editor_access_token: str,
        device: Device,
        rom: Rom,
    ):
        created = client.put(
            "/api/shortcuts",
            json={"device_id": device.id, "rom_id": rom.id},
            headers=_auth(access_token),
        ).json()

        assert (
            client.get(
                f"/api/shortcuts?rom_id={rom.id}", headers=_auth(editor_access_token)
            ).json()
            == []
        )
        assert (
            client.put(
                "/api/shortcuts",
                json={"device_id": device.id, "rom_id": rom.id},
                headers=_auth(editor_access_token),
            ).status_code
            == status.HTTP_404_NOT_FOUND
        )
        assert (
            client.delete(
                f"/api/shortcuts/{created['id']}", headers=_auth(editor_access_token)
            ).status_code
            == status.HTTP_404_NOT_FOUND
        )


class TestDeviceCapabilities:
    def test_update_and_read_launch_capabilities(
        self, client, device_token: str, device: Device
    ):
        response = client.put(
            f"/api/devices/{device.id}",
            json={"launch_capabilities": {"snes": "retroarch:snes9x", "switch": None}},
            headers=_auth(device_token),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["launch_capabilities"] == {
            "snes": "retroarch:snes9x",
            "switch": None,
        }


class TestSteamArtwork:
    def test_rom_without_a_steamgriddb_match_returns_nulls(
        self, client, access_token: str, rom: Rom
    ):
        response = client.get(
            f"/api/shortcuts/artwork/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"url_hero": None, "url_logo": None}

    def test_artwork_comes_from_the_rom_steamgriddb_id(
        self, client, access_token: str, rom: Rom, monkeypatch
    ):
        db_rom_handler.update_rom(rom.id, {"sgdb_id": 4242})
        artwork = AsyncMock(
            return_value={"url_hero": "hero.png", "url_logo": "logo.png"}
        )
        monkeypatch.setattr(
            "endpoints.shortcuts.sgdb_handler.get_steam_artwork", artwork
        )

        response = client.get(
            f"/api/shortcuts/artwork/{rom.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"url_hero": "hero.png", "url_logo": "logo.png"}
        artwork.assert_awaited_once_with(4242)

    def test_unknown_rom_is_404(self, client, access_token: str):
        response = client.get(
            "/api/shortcuts/artwork/999999",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
