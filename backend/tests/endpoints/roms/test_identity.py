import pytest
from fastapi import status
from fastapi.testclient import TestClient

from handler.database import db_platform_handler, db_rom_handler
from models.platform import Platform
from models.rom import Rom, SaveTargetLayout


@pytest.fixture
def switch_platform() -> Platform:
    return db_platform_handler.add_platform(
        Platform(name="Nintendo Switch", slug="switch", fs_slug="switch")
    )


@pytest.fixture
def switch_rom(switch_platform: Platform) -> Rom:
    return db_rom_handler.add_rom(
        Rom(
            platform_id=switch_platform.id,
            name="Game",
            slug="game",
            fs_name="Game.nsp",
            fs_name_no_tags="Game",
            fs_name_no_ext="Game",
            fs_extension="nsp",
            fs_path="switch/roms",
            fs_size_bytes=0,
        )
    )


def test_stores_the_identity_a_client_extracted(
    client: TestClient, access_token: str, switch_rom: Rom
):
    response = client.put(
        f"/api/roms/{switch_rom.id}/identity",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "title_id": "0100ABCD12340000",
            "save_target": "0100ABCD12340000",
            "save_target_layout": "folder-exact",
        },
    )
    assert response.status_code == status.HTTP_200_OK

    stored = db_rom_handler.get_rom(switch_rom.id)
    assert stored is not None
    assert stored.title_id == "0100ABCD12340000"
    assert stored.save_target == "0100ABCD12340000"
    assert stored.save_target_layout == SaveTargetLayout.FOLDER_EXACT


@pytest.mark.parametrize(
    "submitted", ["0100ABCD12340800", "0100ABCD12341001"]  # update, DLC
)
def test_a_switch_update_or_dlc_id_resolves_to_its_base(
    client: TestClient, access_token: str, switch_rom: Rom, submitted: str
):
    """Reassociation matches on this id, so an update id here strands the entry."""
    response = client.put(
        f"/api/roms/{switch_rom.id}/identity",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"title_id": submitted},
    )
    assert response.status_code == status.HTTP_200_OK

    stored = db_rom_handler.get_rom(switch_rom.id)
    assert stored is not None
    assert stored.title_id == "0100ABCD12340000"


def test_a_non_switch_serial_is_stored_verbatim(
    client: TestClient, access_token: str, rom: Rom
):
    response = client.put(
        f"/api/roms/{rom.id}/identity",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"title_id": "SLUS-20152", "save_target": "BASLUS-20152"},
    )
    assert response.status_code == status.HTTP_200_OK

    stored = db_rom_handler.get_rom(rom.id)
    assert stored is not None
    assert stored.title_id == "SLUS-20152"
    assert stored.save_target == "BASLUS-20152"


def test_omitted_fields_are_left_alone(
    client: TestClient, access_token: str, switch_rom: Rom
):
    db_rom_handler.update_rom(
        switch_rom.id,
        {"title_id": "0100ABCD12340000", "save_target": "0100ABCD12340000"},
    )

    response = client.put(
        f"/api/roms/{switch_rom.id}/identity",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"save_target_layout": "folder-exact"},
    )
    assert response.status_code == status.HTTP_200_OK

    stored = db_rom_handler.get_rom(switch_rom.id)
    assert stored is not None
    assert stored.title_id == "0100ABCD12340000"
    assert stored.save_target == "0100ABCD12340000"


def test_an_unknown_rom_is_not_found(client: TestClient, access_token: str):
    response = client.put(
        "/api/roms/99999/identity",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"title_id": "0100ABCD12340000"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_an_unauthenticated_write_is_rejected(client: TestClient, switch_rom: Rom):
    response = client.put(
        f"/api/roms/{switch_rom.id}/identity",
        json={"title_id": "0100ABCD12340000"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
