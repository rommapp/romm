from fastapi.testclient import TestClient
from unittest.mock import patch

from main import app

client = TestClient(app)


def test_get_rom(access_token, rom):
    response = client.get(
        f"/platforms/{rom.p_slug}/roms/{rom.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["id"] == rom.id


def test_get_all_roms(access_token, rom):
    response = client.get(
        f"/platforms/{rom.p_slug}/roms",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200

    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == rom.id


@patch("utils.fs.rename_rom")
def test_update_rom(rename_rom, access_token, rom):
    response = client.patch(
        f"/platforms/{rom.p_slug}/roms/{rom.id}",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"updatedRom": {"file_name": "new_file_name"}},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["rom"]["file_name"] == "new_file_name"

    assert rename_rom.called


def test_delete_roms(access_token, rom):
    response = client.delete(
        f"/platforms/{rom.p_slug}/roms/{rom.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["msg"] == f"{rom.file_name} deleted successfully!"
