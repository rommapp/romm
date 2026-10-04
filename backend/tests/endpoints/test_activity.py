from collections.abc import Iterator
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx2
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from config import OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS
from handler.auth.base_handler import oauth_handler
from handler.database import db_device_handler
from handler.database.base_handler import sync_session
from handler.socket_handler import socket_handler
from models.device import Device
from models.permission import HiddenEntity, PermEntity
from models.platform import Platform
from models.rom import Rom
from models.user import User


def _auth(user: User, scopes: list[str] | None = None) -> dict[str, str]:
    token = oauth_handler.create_access_token(
        data={
            "sub": user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(user.oauth_scopes if scopes is None else scopes),
        },
        expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
    )
    return {"Authorization": f"Bearer {token}"}


def _device(user: User, device_id: str, client: str | None = "grout") -> Device:
    return db_device_handler.add_device(
        Device(id=device_id, user_id=user.id, client=client)
    )


def _hide(entity: PermEntity, entity_id: int, user: User) -> None:
    with sync_session.begin() as session:
        session.add(HiddenEntity(entity=entity, entity_id=entity_id, user_id=user.id))


@pytest.fixture
def emit() -> Iterator[AsyncMock]:
    with patch.object(
        socket_handler.socket_server, "emit", new_callable=AsyncMock
    ) as emit:
        yield emit


def _heartbeat(
    client: TestClient, user: User, device_id: str, rom_id: int
) -> httpx2.Response:
    return client.post(
        "/api/activity/heartbeat",
        headers=_auth(user),
        json={"rom_id": rom_id, "device_id": device_id},
    )


class TestHeartbeat:
    def test_publishes_the_session_for_a_registered_device(
        self, client: TestClient, admin_user: User, rom: Rom, emit: AsyncMock
    ):
        _device(admin_user, "deck")

        response = _heartbeat(client, admin_user, "deck", rom.id)

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["user_id"] == admin_user.id
        assert body["rom_id"] == rom.id
        assert body["device_id"] == "deck"
        assert body["device_type"] == "grout"
        emit.assert_awaited_once_with("activity:update", body)
        listed = client.get("/api/activity", headers=_auth(admin_user)).json()
        assert listed == [body]

    def test_marks_the_device_as_seen(
        self, client: TestClient, admin_user: User, rom: Rom, emit: AsyncMock
    ):
        _device(admin_user, "deck")

        _heartbeat(client, admin_user, "deck", rom.id)

        device = db_device_handler.get_device(device_id="deck", user_id=admin_user.id)
        assert device is not None
        assert device.last_seen is not None

    def test_a_repeat_heartbeat_keeps_the_start_time(
        self, client: TestClient, admin_user: User, rom: Rom, emit: AsyncMock
    ):
        _device(admin_user, "deck")

        first = _heartbeat(client, admin_user, "deck", rom.id).json()
        second = _heartbeat(client, admin_user, "deck", rom.id).json()

        assert second["started_at"] == first["started_at"]

    def test_a_device_without_a_client_is_unknown(
        self, client: TestClient, admin_user: User, rom: Rom, emit: AsyncMock
    ):
        _device(admin_user, "deck", client=None)

        body = _heartbeat(client, admin_user, "deck", rom.id).json()

        assert body["device_type"] == "unknown"

    def test_another_users_device_is_not_found(
        self,
        client: TestClient,
        admin_user: User,
        viewer_user: User,
        rom: Rom,
        emit: AsyncMock,
    ):
        _device(viewer_user, "their-deck")

        response = _heartbeat(client, admin_user, "their-deck", rom.id)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        emit.assert_not_awaited()
        assert client.get("/api/activity", headers=_auth(admin_user)).json() == []

    def test_an_unknown_rom_is_not_found(
        self, client: TestClient, admin_user: User, emit: AsyncMock
    ):
        _device(admin_user, "deck")

        response = _heartbeat(client, admin_user, "deck", 999_999)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "ROM 999999 not found"
        emit.assert_not_awaited()
        device = db_device_handler.get_device(device_id="deck", user_id=admin_user.id)
        assert device is not None
        assert device.last_seen is None

    def test_a_rom_hidden_from_the_player_is_not_found(
        self, client: TestClient, viewer_user: User, rom: Rom, emit: AsyncMock
    ):
        # Hidden ROMs answer 404 everywhere else, so the heartbeat must not
        # hand back the name and cover of one.
        _device(viewer_user, "deck")
        _hide(PermEntity.ROMS, rom.id, viewer_user)

        response = _heartbeat(client, viewer_user, "deck", rom.id)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == f"ROM {rom.id} not found"
        emit.assert_not_awaited()

    @pytest.mark.parametrize(
        "payload",
        [
            {"rom_id": 0, "device_id": "deck"},
            {"rom_id": 1, "device_id": ""},
            {"rom_id": 1, "device_id": "d" * 256},
            {"device_id": "deck"},
        ],
        ids=["rom_zero", "empty_device", "long_device", "no_rom"],
    )
    def test_an_invalid_payload_is_rejected(
        self,
        client: TestClient,
        admin_user: User,
        emit: AsyncMock,
        payload: dict[str, Any],
    ):
        response = client.post(
            "/api/activity/heartbeat", headers=_auth(admin_user), json=payload
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        emit.assert_not_awaited()

    def test_needs_the_write_scope(
        self, client: TestClient, admin_user: User, rom: Rom, emit: AsyncMock
    ):
        _device(admin_user, "deck")

        response = client.post(
            "/api/activity/heartbeat",
            headers=_auth(admin_user, ["roms.user.read"]),
            json={"rom_id": rom.id, "device_id": "deck"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        emit.assert_not_awaited()


class TestClear:
    def test_ends_the_callers_session(
        self, client: TestClient, admin_user: User, rom: Rom, emit: AsyncMock
    ):
        _device(admin_user, "deck")
        _heartbeat(client, admin_user, "deck", rom.id)
        emit.reset_mock()

        response = client.delete(
            "/api/activity/heartbeat",
            headers=_auth(admin_user),
            params={"device_id": "deck"},
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        emit.assert_awaited_once_with(
            "activity:clear",
            {"user_id": admin_user.id, "device_id": "deck", "rom_id": rom.id},
        )
        assert client.get("/api/activity", headers=_auth(admin_user)).json() == []

    def test_leaves_another_users_session_alone(
        self,
        client: TestClient,
        admin_user: User,
        editor_user: User,
        rom: Rom,
        emit: AsyncMock,
    ):
        _device(admin_user, "deck")
        _heartbeat(client, admin_user, "deck", rom.id)
        emit.reset_mock()

        response = client.delete(
            "/api/activity/heartbeat",
            headers=_auth(editor_user),
            params={"device_id": "deck"},
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        emit.assert_not_awaited()
        listed = client.get("/api/activity", headers=_auth(admin_user)).json()
        assert [entry["user_id"] for entry in listed] == [admin_user.id]

    def test_clearing_nothing_broadcasts_nothing(
        self, client: TestClient, admin_user: User, emit: AsyncMock
    ):
        response = client.delete(
            "/api/activity/heartbeat",
            headers=_auth(admin_user),
            params={"device_id": "idle"},
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        emit.assert_not_awaited()


class TestListing:
    @pytest.fixture
    def playing(
        self,
        client: TestClient,
        admin_user: User,
        editor_user: User,
        rom: Rom,
        second_rom: Rom,
        emit: AsyncMock,
    ) -> None:
        _device(admin_user, "deck")
        _device(editor_user, "handheld")
        _heartbeat(client, admin_user, "deck", rom.id)
        _heartbeat(client, editor_user, "handheld", second_rom.id)

    def test_lists_every_users_sessions(
        self,
        client: TestClient,
        viewer_user: User,
        admin_user: User,
        editor_user: User,
        playing: None,
    ):
        listed = client.get("/api/activity", headers=_auth(viewer_user)).json()

        assert {(e["user_id"], e["device_id"]) for e in listed} == {
            (admin_user.id, "deck"),
            (editor_user.id, "handheld"),
        }

    def test_lists_one_roms_sessions(
        self,
        client: TestClient,
        viewer_user: User,
        admin_user: User,
        rom: Rom,
        playing: None,
    ):
        listed = client.get(
            f"/api/activity/rom/{rom.id}", headers=_auth(viewer_user)
        ).json()

        assert [(e["user_id"], e["rom_id"]) for e in listed] == [
            (admin_user.id, rom.id)
        ]

    def test_a_hidden_rom_is_left_out_for_that_user_only(
        self,
        client: TestClient,
        viewer_user: User,
        admin_user: User,
        rom: Rom,
        second_rom: Rom,
        playing: None,
    ):
        _hide(PermEntity.ROMS, rom.id, viewer_user)

        for_viewer = client.get("/api/activity", headers=_auth(viewer_user)).json()
        for_admin = client.get("/api/activity", headers=_auth(admin_user)).json()
        rom_for_viewer = client.get(
            f"/api/activity/rom/{rom.id}", headers=_auth(viewer_user)
        ).json()

        assert [e["rom_id"] for e in for_viewer] == [second_rom.id]
        assert {e["rom_id"] for e in for_admin} == {rom.id, second_rom.id}
        assert rom_for_viewer == []

    def test_a_hidden_platform_hides_its_roms_sessions(
        self,
        client: TestClient,
        viewer_user: User,
        platform: Platform,
        playing: None,
    ):
        _hide(PermEntity.PLATFORMS, platform.id, viewer_user)

        listed = client.get("/api/activity", headers=_auth(viewer_user)).json()

        assert listed == []

    def test_needs_the_read_scope(self, client: TestClient, viewer_user: User):
        response = client.get("/api/activity", headers=_auth(viewer_user, []))

        assert response.status_code == status.HTTP_403_FORBIDDEN
