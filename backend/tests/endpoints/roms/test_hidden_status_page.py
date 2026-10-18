from fastapi import status
from fastapi.testclient import TestClient
from tests.factories import make_rom

from handler.database import db_rom_handler
from models.platform import Platform
from models.rom import Rom
from models.user import User


def _add_rom(admin_user: User, platform: Platform, name: str) -> Rom:
    rom = make_rom(platform, name)
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)
    return rom


def _list(client: TestClient, access_token: str, **params: object) -> dict:
    response = client.get(
        "/api/roms",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"group_by_meta_id": True, **params},
    )
    assert response.status_code == status.HTTP_200_OK
    return response.json()


def test_a_page_picked_with_the_hidden_status_is_not_emptied_on_reload(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
) -> None:
    shown = _add_rom(admin_user, platform, "shown_rom")
    hidden = _add_rom(admin_user, platform, "hidden_rom")
    db_rom_handler.update_rom_user(
        db_rom_handler.get_rom_user(hidden.id, admin_user.id).id, {"hidden": True}
    )

    page = _list(client, access_token, statuses="hidden")

    assert page["total"] == 1
    assert [item["id"] for item in page["items"]] == [hidden.id]
    default_ids = [item["id"] for item in _list(client, access_token)["items"]]
    assert default_ids == [shown.id]
