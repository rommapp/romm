import asyncio

import pytest
from fastapi import status

from endpoints.responses.device_install import InstallRequestSchema
from endpoints.roms import installs
from handler.database.base_handler import sync_session
from handler.device_install_handler import device_install_handler
from models.permission import HiddenEntity, PermEntity
from models.rom import Rom
from models.user import User


@pytest.fixture
def headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def editor_headers(editor_access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {editor_access_token}"}


def _queue(user: User, rom: Rom, device_id: str) -> InstallRequestSchema:
    request, _ = asyncio.run(
        device_install_handler.create(
            user_id=user.id, device_id=device_id, rom_id=rom.id, file_ids=[1]
        )
    )
    return request


def _hide_rom(rom: Rom, user: User) -> None:
    with sync_session.begin() as s:
        s.add(HiddenEntity(entity=PermEntity.ROMS, entity_id=rom.id, user_id=user.id))


class TestRomInstalls:
    def test_lists_the_callers_requests_for_the_rom(
        self, client, headers, admin_user, rom
    ):
        first = _queue(admin_user, rom, "dev-1")
        second = _queue(admin_user, rom, "dev-2")

        response = client.get(f"/api/roms/{rom.id}/installs", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        assert [r["id"] for r in response.json()] == [first.id, second.id]

    def test_another_users_requests_are_not_listed(
        self, client, editor_headers, admin_user, rom
    ):
        _queue(admin_user, rom, "dev-1")

        response = client.get(f"/api/roms/{rom.id}/installs", headers=editor_headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_an_ended_request_is_not_listed(self, client, headers, admin_user, rom):
        request = _queue(admin_user, rom, "dev-1")
        asyncio.run(device_install_handler.cancel(request.id))

        response = client.get(f"/api/roms/{rom.id}/installs", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_a_hidden_rom_is_not_found(self, client, editor_headers, editor_user, rom):
        _hide_rom(rom, editor_user)

        response = client.get(f"/api/roms/{rom.id}/installs", headers=editor_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_is_not_found_while_disabled(self, mocker, client, headers, rom):
        mocker.patch.object(installs, "DEVICE_INSTALL_ENABLED", False)

        response = client.get(f"/api/roms/{rom.id}/installs", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND
